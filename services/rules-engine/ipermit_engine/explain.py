"""Explainability engine for iPermit permit evaluation records (T03-05).

Assembles a ``permit-explanation`` record conforming exactly to
``docs/specs/schemas/permit-explanation.schema.json`` (T00-05) from:

- A **fired** :class:`~ipermit_engine.engine.RuleEvaluation` produced by the
  deterministic rules engine.
- The **rule object dict** (T00-01 shape) that was evaluated.
- Caller-supplied context that the engine itself is DB-free about:
  ``jurisdiction_chain``, ``evaluation_date``, ``ruleset_version``,
  ``inputs_hash``.

The engine only ever needs to build *fired* records (``record_kind = fired``);
negative / not-fired explanations are out of scope for T03-05 but the schema
shapes are shared.

**Reproducibility contract (T00-05 §6).** Identical inputs → byte-identical
record.  No clocks, no randomness. Arrays with incidental order are sorted by
the canonical keys defined in the spec:

- ``citations``       → (citation_type, reference)
- ``known_unknowns``  → (origin, text)
- ``advisories``      → (category, origin, text)

Public API::

    record = build_explanation(
        evaluation=fired_result,
        rule=rule_dict,
        jurisdiction_chain=[...],
        evaluation_date="2026-05-24",
        ruleset_version={"content_hash": "sha256:..."},
        inputs_hash="sha256:...",
    )
    validate(record)  # raises jsonschema.ValidationError on malformed output
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

from .engine import DecisionStep, RuleEvaluation

# ---------------------------------------------------------------------------
# Schema loading (lazy singleton — loaded once and reused)
# ---------------------------------------------------------------------------

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "specs"
    / "schemas"
    / "permit-explanation.schema.json"
)

_SCHEMA: dict[str, Any] | None = None


def _schema() -> dict[str, Any]:
    global _SCHEMA  # noqa: PLW0603
    if _SCHEMA is None:
        _SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TIER_RATIONALE: dict[int, str] = {
    1: "Statutory and fully verified. Stable requirement.",
    2: (
        "Supported and partially verified. May vary by local implementation;"
        " consultant confirmation recommended."
    ),
    3: "Informational only. Requires consultant confirmation before relying on this permit.",
}

_PLATFORM_ADVISORY: dict[str, str] = {
    "text": (
        "Advisory only; not a legal determination. Professional review and"
        " agency confirmation are required before submission."
    ),
    "origin": "platform",
    "category": "advisory_disclaimer",
}

_ENGINE_REVIEW_ADVISORY: dict[str, str] = {
    "text": "Consultant verification recommended before relying on this permit identification.",
    "origin": "engine",
    "category": "professional_review_required",
}

# Evaluation steps in fixed order (spec §5.11).
_EVAL_STEPS = [
    "jurisdiction",
    "temporal_validity",
    "project_type",
    "trigger_conditions",
    "spatial_overlays",
    "dependencies",
]

# Numeric comparison operators (spec §5.5 applicable_thresholds).
_NUMERIC_OPS = frozenset({">", ">=", "<", "<=", "=", "!="})

# Freshness stale threshold in days (T02-07 owner; engine uses 365 as default).
_STALE_THRESHOLD_DAYS = 365


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_explanation(
    *,
    evaluation: RuleEvaluation,
    rule: dict[str, Any],
    jurisdiction_chain: list[dict[str, Any]],
    evaluation_date: str,
    ruleset_version: dict[str, Any],
    inputs_hash: str,
) -> dict[str, Any]:
    """Assemble and validate a permit-explanation record for a fired rule.

    Args:
        evaluation: A *fired* :class:`~ipermit_engine.engine.RuleEvaluation`
            (``evaluation.fired`` must be ``True``).
        rule: The canonical rule object dict (T00-01 shape).
        jurisdiction_chain: Ordered list of jurisdiction dicts, Federal down to
            the most specific applicable jurisdiction.  Each entry must have at
            least ``jurisdiction_id`` and ``jurisdiction_level``.
        evaluation_date: ISO date string (YYYY-MM-DD) passed to the engine.
        ruleset_version: Dict with at least ``content_hash`` (``sha256:<hex>``).
        inputs_hash: sha256 hash of the canonical project inputs (``sha256:<hex>``).

    Returns:
        A dict that validates against ``permit-explanation.schema.json``.

    Raises:
        ValueError: if ``evaluation.fired`` is ``False``.
        jsonschema.ValidationError: if the assembled record fails schema validation.
    """
    if not evaluation.fired:
        raise ValueError(
            f"build_explanation requires a fired RuleEvaluation; "
            f"rule {evaluation.rule_id!r} decided_by={evaluation.decided_by!r}"
        )

    record: dict[str, Any] = {
        "schema_version": "1.0.0",
        "record_kind": "fired",
        "evaluation_date": evaluation_date,
        "ruleset_version": dict(sorted(ruleset_version.items())),
        "rule_refs": _build_rule_refs(rule),
        "jurisdiction_chain": jurisdiction_chain,
        "trigger_path": _build_trigger_path(evaluation),
        "applicable_thresholds": _extract_thresholds(evaluation.evaluated_triggers),
        "citations": _build_citations(rule),
        "confidence": _build_confidence(rule, evaluation_date),
        "known_unknowns": _build_known_unknowns(rule),
        "advisories": _build_advisories(rule),
        "evaluation_trace": _build_evaluation_trace(evaluation),
        "reproducibility": _build_reproducibility(inputs_hash),
    }

    validate(record)
    return record


def validate(record: dict[str, Any]) -> None:
    """Validate *record* against the permit-explanation JSON Schema.

    Raises:
        jsonschema.ValidationError: on the first schema violation found.
    """
    jsonschema.Draft202012Validator(_schema()).validate(record)


# ---------------------------------------------------------------------------
# Assembly helpers — each < 60 lines
# ---------------------------------------------------------------------------


def _build_rule_refs(rule: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the rule_refs array from the rule object."""
    entry: dict[str, Any] = {
        "rule_id": rule["rule_id"],
        "rule_version": rule["version"],
    }
    if rule.get("status") == "archived":
        entry["rule_status_at_evaluation"] = "archived"
    else:
        entry["rule_status_at_evaluation"] = "effective"
    return [entry]


def _build_trigger_path(evaluation: RuleEvaluation) -> dict[str, Any]:
    """Build trigger_path from the engine's evaluated_triggers tree."""
    tree = evaluation.evaluated_triggers
    summary = _summarise_trigger(tree)
    path: dict[str, Any] = {"root": tree}
    if summary:
        path["matched_summary"] = summary[:500]
    return path


def _summarise_trigger(tree: dict[str, Any] | None) -> str:
    """Produce a one-line plain-language summary of the trigger match."""
    if tree is None:
        return ""
    if "field" in tree:
        op = tree.get("operator", "")
        val = tree.get("expected_value", "")
        matched = tree.get("matched", False)
        status = "matched" if matched else "did not match"
        return f"{tree['field']} {op} {val!r} {status}"
    if "all" in tree:
        return (
            "All required conditions matched."
            if tree["matched"]
            else "Not all conditions matched."
        )
    if "any" in tree:
        return (
            "At least one condition matched."
            if tree["matched"]
            else "No conditions matched."
        )
    if "not" in tree:
        return (
            "Negated condition matched."
            if tree["matched"]
            else "Negated condition did not match."
        )
    return "Trigger conditions evaluated."


def _extract_thresholds(
    tree: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Walk the evaluated tree and lift matched numeric-comparison leaves."""
    results: list[dict[str, Any]] = []
    _walk_thresholds(tree, results)
    return results


def _walk_thresholds(
    node: dict[str, Any] | None,
    out: list[dict[str, Any]],
) -> None:
    """Recursively collect threshold entries from an evaluated condition tree."""
    if node is None:
        return
    if "field" in node:
        op = node.get("operator", "")
        if op in _NUMERIC_OPS and "expected_value" in node:
            entry: dict[str, Any] = {
                "field": node["field"],
                "operator": op,
                "threshold_value": node["expected_value"],
                "actual_value": node.get("actual_value"),
            }
            out.append(entry)
        return
    for key in ("all", "any"):
        if key in node:
            for child in node[key]:
                _walk_thresholds(child, out)
    if "not" in node:
        _walk_thresholds(node["not"], out)


def _build_citations(rule: dict[str, Any]) -> list[dict[str, Any]]:
    """Copy citations verbatim from rule.provenance.source_citations, sorted."""
    raw: list[dict[str, Any]] = rule.get("provenance", {}).get("source_citations", [])
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for c in raw:
        key = c["reference"]
        if key not in seen:
            seen.add(key)
            unique.append(dict(c))
    # Spec §6: sort by (citation_type, reference).
    return sorted(unique, key=lambda c: (c.get("citation_type", ""), c["reference"]))


def _build_confidence(rule: dict[str, Any], evaluation_date: str) -> dict[str, Any]:
    """Build the confidence block from the rule's tier and provenance."""
    tier = rule.get("confidence_tier", 3)
    tier_rationale = _tier_rationale_text(rule, tier)
    freshness = _build_freshness(rule, evaluation_date)
    return {"tier": tier, "tier_rationale": tier_rationale, "freshness": freshness}


def _tier_rationale_text(rule: dict[str, Any], tier: int) -> str:
    """Build tier_rationale combining canonical phrasing with rule context."""
    base = _TIER_RATIONALE.get(tier, "Confidence level not specified.")
    extra = rule.get("explanations", {}).get("threshold_summary", "")
    if extra:
        combined = f"{base} {extra.strip()}"
        return combined[:500]
    return base


def _build_freshness(rule: dict[str, Any], evaluation_date: str) -> dict[str, Any]:
    """Compute freshness from rule.provenance.last_verified vs evaluation_date."""
    last_verified = rule.get("provenance", {}).get("last_verified", "")
    days = _days_since(last_verified, evaluation_date)
    stale = days > _STALE_THRESHOLD_DAYS
    freshness: dict[str, Any] = {
        "last_verified": last_verified,
        "days_since_verified": days,
        "stale": stale,
    }
    if stale:
        freshness["stale_reason"] = (
            f"last verified {days} days ago; threshold is {_STALE_THRESHOLD_DAYS}"
        )
    return freshness


def _days_since(last_verified: str, evaluation_date: str) -> int:
    """Compute integer days between two ISO date strings deterministically."""
    try:
        lv = datetime.date.fromisoformat(last_verified)
        ev = datetime.date.fromisoformat(evaluation_date)
        return max(0, (ev - lv).days)
    except (ValueError, TypeError):
        return 0


def _build_known_unknowns(rule: dict[str, Any]) -> list[dict[str, Any]]:
    """Copy rule.known_unknowns, tagged origin=rule, sorted by (origin, text)."""
    raw: list[str] = rule.get("known_unknowns", [])
    entries = [{"text": t, "origin": "rule"} for t in raw if t]
    return sorted(entries, key=lambda e: (e["origin"], e["text"]))


def _build_advisories(rule: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the advisories array: platform + rule advisories + engine advisory."""
    entries: list[dict[str, Any]] = [dict(_PLATFORM_ADVISORY)]
    for text in rule.get("advisories", []):
        if text:
            entries.append(
                {
                    "text": text,
                    "origin": "rule",
                    "category": _infer_advisory_category(text),
                }
            )
    entries.append(dict(_ENGINE_REVIEW_ADVISORY))
    # Spec §6: sort by (category, origin, text).
    return sorted(entries, key=lambda a: (a["category"], a["origin"], a["text"]))


def _infer_advisory_category(text: str) -> str:
    """Heuristically infer advisory category from rule advisory text."""
    lower = text.lower()
    if "coordinate" in lower or "district" in lower or "agency" in lower:
        return "agency_coordination"
    return "professional_review_required"


def _build_evaluation_trace(evaluation: RuleEvaluation) -> list[dict[str, Any]]:
    """Build exactly six evaluation_trace entries based on decided_by."""
    # For a fired rule every step passes. Map DecisionStep → trace step name.
    decided = evaluation.decided_by
    detail_map = _trace_details(evaluation)
    trace: list[dict[str, Any]] = []
    failed_seen = False
    for step in _EVAL_STEPS:
        outcome, detail = _step_outcome(
            step, decided, failed_seen, detail_map, evaluation
        )
        if outcome == "failed":
            failed_seen = True
        entry: dict[str, Any] = {"step": step, "outcome": outcome}
        if detail:
            entry["detail"] = detail
        trace.append(entry)
    return trace


def _trace_details(evaluation: RuleEvaluation) -> dict[str, str]:
    """Return a dict mapping step names to detail strings for fired rules."""
    return {
        "jurisdiction": "Rule jurisdiction present in project jurisdiction_chain.",
        "temporal_validity": "Rule temporal validity confirmed by caller-supplied ruleset.",
        "project_type": "Project type present in applicable_project_types.",
        "trigger_conditions": evaluation.detail,
        "spatial_overlays": "Spatial overlay fields evaluated as context values.",
        "dependencies": "Dependencies deferred to T03-04; not blocking.",
    }


def _step_outcome(
    step: str,
    decided: DecisionStep,
    failed_seen: bool,
    detail_map: dict[str, str],
    evaluation: RuleEvaluation,
) -> tuple[str, str]:
    """Return (outcome, detail) for one trace step."""
    if evaluation.fired:
        return "passed", detail_map.get(step, "")
    if failed_seen:
        return "skipped", ""
    failed_step = _decided_to_trace_step(decided)
    if step == failed_step:
        return "failed", evaluation.detail
    return "passed", detail_map.get(step, "")


def _decided_to_trace_step(decided: DecisionStep) -> str:
    """Map engine DecisionStep enum to the trace step name string."""
    mapping = {
        DecisionStep.JURISDICTION: "jurisdiction",
        DecisionStep.PROJECT_TYPE: "project_type",
        DecisionStep.TRIGGERS: "trigger_conditions",
    }
    return mapping.get(decided, "trigger_conditions")


def _build_reproducibility(inputs_hash: str) -> dict[str, Any]:
    """Build the reproducibility block (deterministic = True always)."""
    return {"inputs_hash": inputs_hash, "deterministic": True}


# ---------------------------------------------------------------------------
# inputs_hash helper
# ---------------------------------------------------------------------------


def hash_inputs(project_inputs: dict[str, Any]) -> str:
    """Compute a deterministic sha256 hash over canonical project inputs.

    Sorts keys recursively before hashing, so the hash is stable regardless of
    dict insertion order.  Returns a ``sha256:<hex>`` string conforming to the
    schema pattern.

    Args:
        project_inputs: Flat or nested mapping of the project's intake fields.

    Returns:
        ``"sha256:<64-hex-chars>"``
    """
    canonical = json.dumps(
        project_inputs, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
