"""Tests for the rule simulation engine (T04-01).

Exercises the three simulation modes (active/direct, hypothetical overlay,
historical replay) plus the ruleset content hash and the bundled
SimulationResult shape, using small synthetic rules.
"""

from __future__ import annotations

from typing import Any

import jsonschema
import pytest
from ipermit_engine import (
    ProjectContext,
    apply_overlay,
    ruleset_content_hash,
    select_governing,
    simulate_project,
)
from ipermit_engine.explain import validate as validate_explanation

CHAIN = [{"jurisdiction_id": "us-tx", "jurisdiction_level": "state"}]
JIDS = ["us-tx"]
TYPES = ["transmission_line"]
DATE = "2026-05-25"


def _rule(
    rule_id: str,
    *,
    field: str = "project.flag",
    tier: int = 1,
    status: str = "draft",
    effective_from: str | None = None,
    version: str = "1.0.0",
) -> dict[str, Any]:
    """A minimal rule dict valid for both the engine and the explainer."""
    rule: dict[str, Any] = {
        "rule_id": rule_id,
        "version": version,
        "status": status,
        "jurisdiction_id": "us-tx",
        "jurisdiction_level": "state",
        "applicable_project_types": ["transmission_line"],
        "confidence_tier": tier,
        "provenance": {
            "source_citations": [
                {"citation_type": "statute", "reference": f"ref-{rule_id}"}
            ],
            "last_verified": "2026-05-20",
        },
        "triggers": {"field": field, "operator": "=", "value": True},
        "outputs": {"permits": [{"name": f"Permit {rule_id}", "agency": "Agency"}]},
        "explanations": {"trigger_explanation": f"{rule_id} fires on {field}."},
    }
    if effective_from:
        rule["effective_from"] = effective_from
    return rule


def _firing_context() -> ProjectContext:
    return ProjectContext.from_namespaces(project={"flag": True, "other": False})


# ---------------------------------------------------------------------------
# Active / direct mode
# ---------------------------------------------------------------------------


def test_simulate_fires_matching_rule_only() -> None:
    rules = [_rule("r-fires"), _rule("r-misses", field="project.other")]
    sim = simulate_project(
        rules=rules,
        context=_firing_context(),
        applicable_jurisdiction_ids=JIDS,
        project_types=TYPES,
        jurisdiction_chain=CHAIN,
        evaluation_date=DATE,
    )
    assert [e.rule_id for e in sim.fired] == ["r-fires"]
    assert [r["rule_id"] for r in sim.fired_rules] == ["r-fires"]


def test_simulation_result_bundles_full_pipeline() -> None:
    sim = simulate_project(
        rules=[_rule("r-fires", tier=3)],
        context=_firing_context(),
        applicable_jurisdiction_ids=JIDS,
        project_types=TYPES,
        jurisdiction_chain=CHAIN,
        evaluation_date=DATE,
    )
    assert sim.ruleset_version["content_hash"].startswith("sha256:")
    assert sim.inputs_hash.startswith("sha256:")
    assert len(sim.explanations) == 1
    validate_explanation(sim.explanations[0])  # bundled record is schema-valid
    assert sim.resolution.requirements  # one applicable requirement
    assert sim.sequencing.stages  # one stage
    assert "r-fires" in sim.known_unknowns  # tier 3 -> low_confidence item present
    assert any(k.category == "low_confidence" for k in sim.known_unknowns["r-fires"])


def test_no_fired_rules_yields_empty_bundle() -> None:
    sim = simulate_project(
        rules=[_rule("r-misses", field="project.other")],
        context=_firing_context(),
        applicable_jurisdiction_ids=JIDS,
        project_types=TYPES,
        jurisdiction_chain=CHAIN,
        evaluation_date=DATE,
    )
    assert sim.fired == ()
    assert sim.explanations == ()
    assert sim.resolution.requirements == ()


# ---------------------------------------------------------------------------
# Hypothetical overlay mode
# ---------------------------------------------------------------------------


def test_apply_overlay_upsert_and_remove() -> None:
    base = [_rule("rule-a"), _rule("rule-b")]
    replacement = _rule("rule-a", field="project.other")
    result = apply_overlay(base, {"upsert": [replacement], "remove": ["rule-b"]})
    assert [r["rule_id"] for r in result] == ["rule-a"]
    assert result[0]["triggers"]["field"] == "project.other"


def test_overlay_removes_a_rule_from_simulation() -> None:
    base = [_rule("rule-a"), _rule("rule-b")]
    sim = simulate_project(
        rules=base,
        context=_firing_context(),
        applicable_jurisdiction_ids=JIDS,
        project_types=TYPES,
        jurisdiction_chain=CHAIN,
        evaluation_date=DATE,
        overlay={"remove": ["rule-b"]},
    )
    assert [e.rule_id for e in sim.fired] == ["rule-a"]


# ---------------------------------------------------------------------------
# Historical replay (temporal selection)
# ---------------------------------------------------------------------------


def test_select_governing_filters_status_and_window() -> None:
    rules = [
        _rule("rule-eff", status="effective", effective_from="2020-01-01"),
        _rule("rule-future", status="effective", effective_from="2030-01-01"),
        _rule("draft-only", status="draft"),
    ]
    governing = select_governing(rules, DATE)
    assert [r["rule_id"] for r in governing] == ["rule-eff"]


def test_governing_only_excludes_draft_and_future() -> None:
    rules = [
        _rule("rule-eff", status="effective", effective_from="2020-01-01"),
        _rule("rule-future", status="effective", effective_from="2030-01-01"),
        _rule("draft-only", status="draft"),
    ]
    sim = simulate_project(
        rules=rules,
        context=_firing_context(),
        applicable_jurisdiction_ids=JIDS,
        project_types=TYPES,
        jurisdiction_chain=CHAIN,
        evaluation_date=DATE,
        governing_only=True,
    )
    assert [e.rule_id for e in sim.fired] == ["rule-eff"]


def test_select_governing_picks_highest_version_on_same_date() -> None:
    rules = [
        _rule(
            "rule-dup", status="effective", effective_from="2020-01-01", version="1.0.0"
        ),
        _rule(
            "rule-dup", status="effective", effective_from="2020-01-01", version="2.1.0"
        ),
    ]
    governing = select_governing(rules, DATE)
    assert len(governing) == 1
    assert governing[0]["version"] == "2.1.0"


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------


def test_ruleset_content_hash_is_order_independent() -> None:
    rules = [_rule("a"), _rule("b"), _rule("c")]
    assert ruleset_content_hash(rules) == ruleset_content_hash(list(reversed(rules)))


def test_ruleset_content_hash_changes_with_content() -> None:
    base = [_rule("a")]
    changed = [_rule("a", tier=2)]
    assert ruleset_content_hash(base) != ruleset_content_hash(changed)


def test_simulate_rejects_unknown_namespace() -> None:
    with pytest.raises(ValueError, match="unknown namespace"):
        ProjectContext.from_namespaces(bogus={"x": 1})


@pytest.mark.parametrize("bad", [{"schema_version": "1.0.0"}])
def test_validate_explanation_rejects_malformed(bad: dict[str, Any]) -> None:
    with pytest.raises(jsonschema.ValidationError):
        validate_explanation(bad)
