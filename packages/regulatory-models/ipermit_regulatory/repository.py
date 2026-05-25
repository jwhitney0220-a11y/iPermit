"""Convert, validate, and store regulatory rule objects (T02-02).

Bridges the canonical rule object (T00-01 JSON shape) and the ORM models.
Records are validated against docs/specs/schemas/rule-object.schema.json before
they enter the database, so the database never holds a document that violates
the standard.
"""

from __future__ import annotations

import datetime
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from sqlalchemy.orm import Session

from .models import RegulatoryCitation, RegulatoryRule

_SCHEMA_REL = "docs/specs/schemas/rule-object.schema.json"


def _repo_root() -> Path:
    """Find the repo root by walking up to the canonical schema file."""
    for parent in Path(__file__).resolve().parents:
        if (parent / _SCHEMA_REL).is_file():
            return parent
    raise FileNotFoundError(f"could not locate {_SCHEMA_REL}")


@lru_cache(maxsize=1)
def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads((_repo_root() / _SCHEMA_REL).read_text())
    return jsonschema.Draft202012Validator(schema)


def validate_rule(data: dict[str, Any]) -> None:
    """Raise jsonschema.ValidationError if the document violates T00-01."""
    _validator().validate(data)


def _date(value: str | None) -> datetime.date | None:
    return datetime.date.fromisoformat(value) if value else None


def _build_citations(
    rule_id: str, version: str, provenance: dict[str, Any]
) -> list[RegulatoryCitation]:
    """Build RegulatoryCitation rows from a provenance sub-object."""
    citations = []
    for raw in provenance.get("source_citations", []):
        citations.append(
            RegulatoryCitation(
                rule_id=rule_id,
                version=version,
                citation_type=raw["citation_type"],
                reference=raw["reference"],
                url=raw.get("url"),
                retrieved_at=_date(raw.get("retrieved_at")),
            )
        )
    return citations


def _build_rule(data: dict[str, Any]) -> RegulatoryRule:
    """Build a RegulatoryRule ORM object from a (validated) canonical document."""
    provenance = data["provenance"]
    rule = RegulatoryRule(
        rule_id=data["rule_id"],
        version=data["version"],
        title=data["title"],
        permit_name=data["permit_name"],
        permit_code=data.get("permit_code"),
        jurisdiction_level=data["jurisdiction_level"],
        jurisdiction_id=data["jurisdiction_id"],
        source_agency=data["source_agency"],
        confidence_tier=data["confidence_tier"],
        status=data["status"],
        effective_from=_date(data.get("effective_from")),
        effective_to=_date(data.get("effective_to")),
        last_verified=datetime.date.fromisoformat(provenance["last_verified"]),
        reviewer=provenance.get("reviewer"),
        applicable_project_types=list(data["applicable_project_types"]),
        document=data,
    )
    rule.citations = _build_citations(data["rule_id"], data["version"], provenance)
    return rule


def add_rule(session: Session, data: dict[str, Any]) -> RegulatoryRule:
    """Validate a canonical rule document and add it to the session."""
    validate_rule(data)
    rule = _build_rule(data)
    session.add(rule)
    return rule


def to_document(rule: RegulatoryRule) -> dict[str, Any]:
    """Return the stored canonical document for a RegulatoryRule."""
    return dict(rule.document)


def get_rule(session: Session, rule_id: str, version: str) -> RegulatoryRule | None:
    """Retrieve a single RegulatoryRule by (rule_id, version), or None."""
    return session.get(RegulatoryRule, (rule_id, version))
