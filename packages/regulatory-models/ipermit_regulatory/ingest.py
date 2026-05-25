"""Dataset ingestion pipeline for regulatory rules (T02-06).

Reads structured rows from CSV or JSON, normalizes each row into a canonical
rule object, validates against rule-object.schema.json, and persists via
repository.add_rule.

Public API
----------
- load_rules_from_json(path, session, *, dry_run) -> list[dict]
- load_rules_from_csv(path, session, *, dry_run)  -> list[dict]
- normalize(row) -> dict

Each function raises ``IngestError`` (a plain ``ValueError`` subclass) on
per-row failures, including the row index and the offending field so the caller
can surface a useful message without catching jsonschema internals.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import jsonschema
from sqlalchemy.orm import Session

from .repository import add_rule, validate_rule

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class IngestError(ValueError):
    """Raised when a row fails normalization or schema validation.

    Attributes
    ----------
    row_index:
        Zero-based position of the offending row in the source file.
    field:
        The offending field name or path, if identifiable.
    """

    def __init__(self, row_index: int, field: str, message: str) -> None:
        self.row_index = row_index
        self.field = field
        super().__init__(f"row {row_index}: field '{field}': {message}")


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _split_list(value: str | list | None) -> list[str]:
    """Coerce a pipe-separated string or list to a list of stripped strings."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split("|") if v.strip()]


def _int_or_none(value: Any) -> int | None:
    """Coerce a value to int, returning None on falsy input."""
    if value is None or value == "":
        return None
    return int(value)


def _str_or_none(value: Any) -> str | None:
    """Return a non-empty string or None."""
    s = str(value).strip() if value is not None else ""
    return s if s else None


def _parse_citation(raw: Any) -> dict[str, Any]:
    """Parse a citation from a dict or JSON string."""
    if isinstance(raw, dict):
        return raw
    return json.loads(str(raw))


def _normalise_level(raw: str | None) -> str | None:
    """Map kebab-case jurisdiction_level to schema snake_case.

    The schema enum uses snake_case (e.g. ``river_authority``).  Spreadsheets
    often produce kebab-case (e.g. ``river-authority``) because it matches the
    jurisdiction ID segment.  Both forms are accepted and normalised.
    """
    if not raw:
        return None
    return raw.strip().replace("-", "_")


def _build_provenance(row: dict[str, Any]) -> dict[str, Any]:
    """Assemble the provenance sub-object from a flat or nested row."""
    if "provenance" in row and isinstance(row["provenance"], dict):
        return row["provenance"]
    raw_cits = row.get("source_citations", [])
    if isinstance(raw_cits, str):
        try:
            raw_cits = json.loads(raw_cits)
        except json.JSONDecodeError:
            raw_cits = []
    citations = [_parse_citation(c) for c in raw_cits] if raw_cits else []
    prov: dict[str, Any] = {
        "source_citations": citations,
        "last_verified": str(row.get("last_verified", "")).strip(),
    }
    if reviewer := _str_or_none(row.get("reviewer")):
        prov["reviewer"] = reviewer
    if notes := _str_or_none(row.get("reviewer_notes")):
        prov["reviewer_notes"] = notes
    return prov


def _build_nested(row: dict[str, Any], key: str) -> Any:
    """Return a nested dict/list from a row key, parsing JSON strings if needed."""
    val = row.get(key)
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(str(val))
    except json.JSONDecodeError:
        return None


def _apply_scalars(doc: dict[str, Any], row: dict[str, Any]) -> None:
    """Copy scalar identity/classification fields from row into doc."""
    for key in (
        "rule_id",
        "version",
        "title",
        "permit_name",
        "jurisdiction_id",
        "source_agency",
        "status",
    ):
        if val := _str_or_none(row.get(key)):
            doc[key] = val

    if level := _normalise_level(row.get("jurisdiction_level")):
        doc["jurisdiction_level"] = level

    if pc := _str_or_none(row.get("permit_code")):
        doc["permit_code"] = pc
    doc["applicable_project_types"] = _split_list(row.get("applicable_project_types"))
    ct = _int_or_none(row.get("confidence_tier"))
    if ct is not None:
        doc["confidence_tier"] = ct


def _apply_optional_arrays(doc: dict[str, Any], row: dict[str, Any]) -> None:
    """Coerce and attach optional list fields to doc."""
    for key in ("supersedes", "known_unknowns", "advisories", "tags"):
        val = row.get(key)
        if isinstance(val, list):
            doc[key] = val
        elif val and isinstance(val, str):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    doc[key] = parsed
            except json.JSONDecodeError:
                pass

    if superseded_by := _str_or_none(row.get("superseded_by")):
        doc["superseded_by"] = superseded_by
    if notes := _str_or_none(row.get("notes")):
        doc["notes"] = notes


def normalize(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a flat or structured row dict into a canonical rule object.

    Handles:
    - pipe-separated ``applicable_project_types`` strings from CSV
    - JSON-string columns for ``triggers``, ``outputs``, ``explanations``,
      ``provenance``, ``source_citations``
    - type coercion for ``confidence_tier`` (int) and date strings
    - optional fields omitted when blank/null

    Returns a dict ready to pass to ``validate_rule`` / ``add_rule``.
    """
    doc: dict[str, Any] = {}
    _apply_scalars(doc, row)

    for date_key in ("effective_from", "effective_to"):
        if dv := _str_or_none(row.get(date_key)):
            doc[date_key] = dv

    doc["provenance"] = _build_provenance(row)

    for key in ("triggers", "outputs", "explanations", "sequencing"):
        val = _build_nested(row, key)
        if val is not None:
            doc[key] = val

    _apply_optional_arrays(doc, row)
    return doc


# ---------------------------------------------------------------------------
# Row-level load helper
# ---------------------------------------------------------------------------


def _load_one(
    row: dict[str, Any],
    idx: int,
    session: Session | None,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Normalize, validate, and optionally persist one row.

    Wraps jsonschema.ValidationError in IngestError so callers get a
    consistent, row-indexed error type regardless of which step fails.
    """
    try:
        doc = normalize(row)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IngestError(idx, "<normalization>", str(exc)) from exc

    try:
        if dry_run or session is None:
            validate_rule(doc)
        else:
            add_rule(session, doc)
    except jsonschema.ValidationError as exc:
        field = ".".join(str(p) for p in exc.absolute_path) or exc.validator_value
        raise IngestError(idx, str(field), exc.message) from exc

    return doc


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def load_rules_from_json(
    path: str | Path,
    session: Session | None = None,
    *,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Load rule definitions from a JSON file (object or array of objects).

    Parameters
    ----------
    path:
        Path to a JSON file containing a single rule object or a list of them.
    session:
        SQLAlchemy session. Required unless ``dry_run=True``.
    dry_run:
        When True, validates every row but writes nothing to the database.

    Returns
    -------
    list of normalized canonical dicts (one per row).

    Raises
    ------
    IngestError
        On the first row that fails normalization or schema validation.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = raw if isinstance(raw, list) else [raw]
    results: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        doc = _load_one(row, idx, session, dry_run=dry_run)
        results.append(doc)
    return results


def load_rules_from_csv(
    path: str | Path,
    session: Session | None = None,
    *,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Load rule definitions from a CSV file using the rule-template header.

    Each CSV row becomes one rule. Columns that hold JSON (``triggers``,
    ``outputs``, ``explanations``, ``source_citations``, etc.) must be
    valid JSON strings in the cell. Pipe-delimited strings are accepted
    for ``applicable_project_types``.

    Parameters
    ----------
    path:
        Path to a CSV file whose header matches ``templates/ingestion/rule-template.csv``.
    session:
        SQLAlchemy session. Required unless ``dry_run=True``.
    dry_run:
        When True, validates every row but writes nothing to the database.

    Returns
    -------
    list of normalized canonical dicts (one per row).

    Raises
    ------
    IngestError
        On the first row that fails normalization or schema validation.
    """
    results: list[dict[str, Any]] = []
    with Path(path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for idx, row in enumerate(reader):
            # Skip rows that are purely comment lines (# prefix in first col)
            first_val = next(iter(row.values()), "") or ""
            if first_val.strip().startswith("#"):
                continue
            doc = _load_one(dict(row), idx, session, dry_run=dry_run)
            results.append(doc)
    return results
