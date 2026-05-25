"""Tests for the explainability engine (T03-05).

Evaluates the canonical CWA-404 example rule through ipermit_engine to get a
fired RuleEvaluation, builds the explanation record, and asserts:

- The record validates against permit-explanation.schema.json.
- Key fields are correctly populated (rule_id, trigger_path.root, citations,
  confidence_tier, evaluation_trace).
- Determinism: identical inputs produce equal dicts across two calls.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from ipermit_engine import DecisionStep, ProjectContext, RuleEvaluation, evaluate_rule
from ipermit_engine.explain import build_explanation, hash_inputs, validate

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CWA_JURISDICTION = "us-federal"
CWA_TYPE = "transmission_line"
EVALUATION_DATE = "2026-05-24"
RULESET_VERSION = {
    "content_hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "commit_sha": "c00e404",
    "snapshot_label": "2026-05-24-effective",
}
JURISDICTION_CHAIN = [
    {
        "jurisdiction_id": "us-federal",
        "jurisdiction_level": "federal",
        "canonical_name": "United States Federal",
        "detection_source": "user_input",
    },
    {
        "jurisdiction_id": "us-tx",
        "jurisdiction_level": "state",
        "canonical_name": "State of Texas",
        "detection_source": "gis_auto_detect",
    },
    {
        "jurisdiction_id": "us-tx-travis-county",
        "jurisdiction_level": "county",
        "canonical_name": "Travis County, Texas",
        "detection_source": "user_confirmed",
    },
]


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "specs" / "examples").is_dir():
            return parent
    raise FileNotFoundError("repo root not found")


@pytest.fixture(scope="module")
def cwa_rule() -> dict[str, Any]:
    """Load the canonical CWA-404 example rule object."""
    path = _repo_root() / "docs/specs/examples/rule-object-example.json"
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    """Load the permit-explanation JSON Schema."""
    path = _repo_root() / "docs/specs/schemas/permit-explanation.schema.json"
    return json.loads(path.read_text())


def _firing_context() -> ProjectContext:
    """Context that fires CWA-404: federal nexus + one stream crossing."""
    return ProjectContext(
        {
            "project.federal_nexus": True,
            "project.stream_crossings_count": 1,
            "project.has_wetlands": False,
        }
    )


@pytest.fixture(scope="module")
def fired_evaluation(cwa_rule: dict[str, Any]) -> Any:
    """A fired RuleEvaluation from the CWA-404 rule."""
    return evaluate_rule(cwa_rule, _firing_context(), [CWA_JURISDICTION], [CWA_TYPE])


@pytest.fixture(scope="module")
def explanation(cwa_rule: dict[str, Any], fired_evaluation: Any) -> dict[str, Any]:
    """A fully built permit-explanation record from the CWA-404 example."""
    inputs_hash = hash_inputs(_firing_context().as_dict())
    return build_explanation(
        evaluation=fired_evaluation,
        rule=cwa_rule,
        jurisdiction_chain=JURISDICTION_CHAIN,
        evaluation_date=EVALUATION_DATE,
        ruleset_version=RULESET_VERSION,
        inputs_hash=inputs_hash,
    )


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_explanation_validates_against_schema(
    explanation: dict[str, Any], schema: dict[str, Any]
) -> None:
    """The produced record must pass JSON Schema draft 2020-12 validation."""
    jsonschema.Draft202012Validator(schema).validate(explanation)


def test_validate_helper_does_not_raise(explanation: dict[str, Any]) -> None:
    """The public validate() helper must not raise for a valid record."""
    validate(explanation)  # should be a no-op for a valid record


def test_validate_raises_for_malformed_record() -> None:
    """validate() must raise jsonschema.ValidationError for a bad record."""
    with pytest.raises(jsonschema.ValidationError):
        validate({"schema_version": "1.0.0"})  # missing many required fields


# ---------------------------------------------------------------------------
# Identity & versioning fields
# ---------------------------------------------------------------------------


def test_schema_version(explanation: dict[str, Any]) -> None:
    assert explanation["schema_version"] == "1.0.0"


def test_record_kind_fired(explanation: dict[str, Any]) -> None:
    assert explanation["record_kind"] == "fired"


def test_evaluation_date(explanation: dict[str, Any]) -> None:
    assert explanation["evaluation_date"] == EVALUATION_DATE


def test_ruleset_version_passthrough(explanation: dict[str, Any]) -> None:
    assert (
        explanation["ruleset_version"]["content_hash"]
        == RULESET_VERSION["content_hash"]
    )


# ---------------------------------------------------------------------------
# rule_refs
# ---------------------------------------------------------------------------


def test_rule_id_in_rule_refs(explanation: dict[str, Any]) -> None:
    """rule_refs must contain the CWA-404 rule_id."""
    ids = [r["rule_id"] for r in explanation["rule_refs"]]
    assert "us-federal-cwa-section-404-usace-permit" in ids


def test_rule_version_in_rule_refs(explanation: dict[str, Any]) -> None:
    """rule_refs must carry the semver from the rule object."""
    ref = explanation["rule_refs"][0]
    assert ref["rule_version"] == "1.0.0"


def test_rule_status_effective(explanation: dict[str, Any]) -> None:
    """Effective rules must be tagged effective in rule_refs."""
    ref = explanation["rule_refs"][0]
    assert ref["rule_status_at_evaluation"] == "effective"


# ---------------------------------------------------------------------------
# trigger_path
# ---------------------------------------------------------------------------


def test_trigger_path_root_present(explanation: dict[str, Any]) -> None:
    """trigger_path.root must be present for a fired record."""
    assert "trigger_path" in explanation
    assert "root" in explanation["trigger_path"]


def test_trigger_path_root_is_all_matched(explanation: dict[str, Any]) -> None:
    """Root node must be an all-composite that matched."""
    root = explanation["trigger_path"]["root"]
    assert "all" in root
    assert root["matched"] is True


def test_trigger_path_first_leaf(explanation: dict[str, Any]) -> None:
    """First leaf must reflect federal_nexus = true, matched."""
    leaf = explanation["trigger_path"]["root"]["all"][0]
    assert leaf["field"] == "project.federal_nexus"
    assert leaf["matched"] is True
    assert leaf["actual_value"] is True


def test_trigger_path_any_branch_matched(explanation: dict[str, Any]) -> None:
    """Second all-child is an any whose stream_crossings leaf matched."""
    any_node = explanation["trigger_path"]["root"]["all"][1]
    assert "any" in any_node
    assert any_node["matched"] is True
    stream_leaf = any_node["any"][0]
    assert stream_leaf["field"] == "project.stream_crossings_count"
    assert stream_leaf["matched"] is True


def test_matched_summary_present_and_bounded(explanation: dict[str, Any]) -> None:
    """matched_summary must be present and <= 500 chars."""
    summary = explanation["trigger_path"].get("matched_summary", "")
    assert isinstance(summary, str)
    assert len(summary) <= 500


# ---------------------------------------------------------------------------
# applicable_thresholds
# ---------------------------------------------------------------------------


def test_applicable_thresholds_stream_crossings(explanation: dict[str, Any]) -> None:
    """The stream_crossings_count > 0 threshold must be lifted."""
    thresholds = explanation.get("applicable_thresholds", [])
    fields = [t["field"] for t in thresholds]
    assert "project.stream_crossings_count" in fields
    threshold = next(
        t for t in thresholds if t["field"] == "project.stream_crossings_count"
    )
    assert threshold["operator"] == ">"
    assert threshold["threshold_value"] == 0
    assert threshold["actual_value"] == 1


# ---------------------------------------------------------------------------
# citations
# ---------------------------------------------------------------------------


def test_citations_non_empty(explanation: dict[str, Any]) -> None:
    """citations must have at least one entry for a fired rule."""
    assert len(explanation.get("citations", [])) >= 1


def test_citations_copied_from_rule(
    explanation: dict[str, Any], cwa_rule: dict[str, Any]
) -> None:
    """Every rule citation reference must appear in the explanation citations."""
    rule_refs = {c["reference"] for c in cwa_rule["provenance"]["source_citations"]}
    explanation_refs = {c["reference"] for c in explanation["citations"]}
    assert rule_refs == explanation_refs


def test_citations_sorted_by_type_then_reference(explanation: dict[str, Any]) -> None:
    """citations must be sorted by (citation_type, reference) per spec §6."""
    citations = explanation["citations"]
    keys = [(c.get("citation_type", ""), c["reference"]) for c in citations]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# confidence
# ---------------------------------------------------------------------------


def test_confidence_tier_is_1(explanation: dict[str, Any]) -> None:
    """CWA-404 is a Tier 1 rule; confidence.tier must be 1."""
    assert explanation["confidence"]["tier"] == 1


def test_confidence_tier_rationale_present(explanation: dict[str, Any]) -> None:
    """tier_rationale must be a non-empty string containing canonical phrasing."""
    rationale = explanation["confidence"]["tier_rationale"]
    assert isinstance(rationale, str) and len(rationale) > 0
    assert "Statutory and fully verified" in rationale


def test_freshness_last_verified(explanation: dict[str, Any]) -> None:
    """last_verified must match the rule's provenance.last_verified."""
    assert explanation["confidence"]["freshness"]["last_verified"] == "2026-05-20"


def test_freshness_not_stale(explanation: dict[str, Any]) -> None:
    """4 days since verified is well below the 365-day threshold."""
    freshness = explanation["confidence"]["freshness"]
    assert freshness["stale"] is False
    assert freshness["days_since_verified"] == 4


# ---------------------------------------------------------------------------
# known_unknowns
# ---------------------------------------------------------------------------


def test_known_unknowns_from_rule(
    explanation: dict[str, Any], cwa_rule: dict[str, Any]
) -> None:
    """All rule known_unknowns must be present in the explanation."""
    rule_texts = set(cwa_rule.get("known_unknowns", []))
    explanation_texts = {ku["text"] for ku in explanation.get("known_unknowns", [])}
    assert rule_texts <= explanation_texts


def test_known_unknowns_origin_rule(explanation: dict[str, Any]) -> None:
    """Entries copied from the rule must carry origin='rule'."""
    for ku in explanation.get("known_unknowns", []):
        if ku.get("origin") == "rule":
            assert "engine_signal" not in ku


def test_known_unknowns_sorted(explanation: dict[str, Any]) -> None:
    """known_unknowns must be sorted by (origin, text) per spec §6."""
    kus = explanation.get("known_unknowns", [])
    keys = [(k["origin"], k["text"]) for k in kus]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# advisories
# ---------------------------------------------------------------------------


def test_advisories_non_empty(explanation: dict[str, Any]) -> None:
    """At least one advisory is always required per AGENTS.md."""
    assert len(explanation.get("advisories", [])) >= 1


def test_platform_advisory_present(explanation: dict[str, Any]) -> None:
    """The standing platform advisory must be present on every record."""
    texts = [a["text"] for a in explanation["advisories"]]
    assert any("not a legal determination" in t for t in texts)


def test_platform_advisory_origin(explanation: dict[str, Any]) -> None:
    """The platform advisory must carry origin='platform'."""
    platform_advisories = [
        a for a in explanation["advisories"] if a["origin"] == "platform"
    ]
    assert len(platform_advisories) >= 1


def test_advisories_sorted(explanation: dict[str, Any]) -> None:
    """advisories must be sorted by (category, origin, text) per spec §6."""
    advisories = explanation["advisories"]
    keys = [(a["category"], a["origin"], a["text"]) for a in advisories]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# evaluation_trace
# ---------------------------------------------------------------------------


def test_evaluation_trace_exactly_six_steps(explanation: dict[str, Any]) -> None:
    """evaluation_trace must have exactly 6 entries."""
    assert len(explanation["evaluation_trace"]) == 6


def test_evaluation_trace_all_passed_for_fired(explanation: dict[str, Any]) -> None:
    """A fired record must have all six steps passed."""
    outcomes = [s["outcome"] for s in explanation["evaluation_trace"]]
    assert outcomes == ["passed"] * 6


def test_evaluation_trace_step_order(explanation: dict[str, Any]) -> None:
    """Steps must be in the fixed order defined by spec §5.11."""
    expected_steps = [
        "jurisdiction",
        "temporal_validity",
        "project_type",
        "trigger_conditions",
        "spatial_overlays",
        "dependencies",
    ]
    actual_steps = [s["step"] for s in explanation["evaluation_trace"]]
    assert actual_steps == expected_steps


# ---------------------------------------------------------------------------
# reproducibility
# ---------------------------------------------------------------------------


def test_reproducibility_deterministic_true(explanation: dict[str, Any]) -> None:
    """reproducibility.deterministic must always be True."""
    assert explanation["reproducibility"]["deterministic"] is True


def test_inputs_hash_format(explanation: dict[str, Any]) -> None:
    """inputs_hash must match the sha256:<64-hex-chars> pattern."""
    h = explanation["reproducibility"]["inputs_hash"]
    assert re.match(r"^sha256:[0-9a-f]{64}$", h)


# ---------------------------------------------------------------------------
# Determinism contract (T00-05 §6)
# ---------------------------------------------------------------------------


def test_determinism_identical_inputs(cwa_rule: dict[str, Any]) -> None:
    """Two calls with identical inputs must produce byte-identical records."""
    ctx = _firing_context()
    inputs_hash = hash_inputs(ctx.as_dict())
    evaluation = evaluate_rule(cwa_rule, ctx, [CWA_JURISDICTION], [CWA_TYPE])

    record_a = build_explanation(
        evaluation=evaluation,
        rule=cwa_rule,
        jurisdiction_chain=JURISDICTION_CHAIN,
        evaluation_date=EVALUATION_DATE,
        ruleset_version=RULESET_VERSION,
        inputs_hash=inputs_hash,
    )
    record_b = build_explanation(
        evaluation=evaluation,
        rule=cwa_rule,
        jurisdiction_chain=JURISDICTION_CHAIN,
        evaluation_date=EVALUATION_DATE,
        ruleset_version=RULESET_VERSION,
        inputs_hash=inputs_hash,
    )
    assert record_a == record_b, "Identical inputs must produce identical records."


def test_determinism_as_json(cwa_rule: dict[str, Any]) -> None:
    """JSON serialization of two identical records must be byte-identical."""
    ctx = _firing_context()
    inputs_hash = hash_inputs(ctx.as_dict())
    evaluation = evaluate_rule(cwa_rule, ctx, [CWA_JURISDICTION], [CWA_TYPE])

    kwargs = {
        "evaluation": evaluation,
        "rule": cwa_rule,
        "jurisdiction_chain": JURISDICTION_CHAIN,
        "evaluation_date": EVALUATION_DATE,
        "ruleset_version": RULESET_VERSION,
        "inputs_hash": inputs_hash,
    }
    json_a = json.dumps(build_explanation(**kwargs), sort_keys=True)
    json_b = json.dumps(build_explanation(**kwargs), sort_keys=True)
    assert json_a == json_b


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_build_explanation_raises_for_non_fired(cwa_rule: dict[str, Any]) -> None:
    """build_explanation must raise ValueError when evaluation.fired is False."""
    non_fired = RuleEvaluation(
        rule_id=cwa_rule["rule_id"],
        fired=False,
        decided_by=DecisionStep.JURISDICTION,
        evaluated_triggers=None,
        detail="jurisdiction not in chain",
    )
    with pytest.raises(ValueError, match="fired"):
        build_explanation(
            evaluation=non_fired,
            rule=cwa_rule,
            jurisdiction_chain=JURISDICTION_CHAIN,
            evaluation_date=EVALUATION_DATE,
            ruleset_version=RULESET_VERSION,
            inputs_hash="sha256:" + "0" * 64,
        )


def test_hash_inputs_deterministic() -> None:
    """hash_inputs must produce the same hash for the same dict regardless of insertion order."""
    inputs_a = {"project.federal_nexus": True, "project.acreage": 12.5}
    inputs_b = {"project.acreage": 12.5, "project.federal_nexus": True}
    assert hash_inputs(inputs_a) == hash_inputs(inputs_b)


def test_hash_inputs_format() -> None:
    """hash_inputs must return a sha256:<64-hex> string."""
    result = hash_inputs({"project.flag": True})
    assert re.match(r"^sha256:[0-9a-f]{64}$", result)
