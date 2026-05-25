"""Tests for the edge-case analysis primitives (T04-03).

Exercises the four edge categories the QA/QC process guards against:
incomplete project data, ambiguous thresholds, overlapping jurisdictions, and
conflicting-trigger determinism.
"""

from __future__ import annotations

import json
from typing import Any

from ipermit_engine import (
    ProjectContext,
    apply_operator,
    boundary_probe_values,
    find_missing_inputs,
    numeric_threshold_leaves,
    overlapping_requirements,
    simulate_project,
)
from ipermit_rules import load_rules

DATE = "2026-05-25"


def _rule(
    rule_id: str,
    *,
    triggers: dict[str, Any],
    jid: str = "us-tx",
    level: str = "state",
    permit: str = "Some Permit",
    agency: str = "Some Agency",
) -> dict[str, Any]:
    """A minimal rule dict valid for the engine and the explainer."""
    return {
        "rule_id": rule_id,
        "version": "1.0.0",
        "status": "draft",
        "jurisdiction_id": jid,
        "jurisdiction_level": level,
        "applicable_project_types": ["transmission_line"],
        "confidence_tier": 1,
        "provenance": {
            "source_citations": [{"citation_type": "statute", "reference": rule_id}],
            "last_verified": "2026-05-20",
        },
        "triggers": triggers,
        "outputs": {"permits": [{"name": permit, "agency": agency}]},
        "explanations": {"trigger_explanation": f"{rule_id} explanation."},
    }


def _chain(jids: list[str]) -> list[dict[str, str]]:
    return [{"jurisdiction_id": j, "jurisdiction_level": "state"} for j in jids]


# ---------------------------------------------------------------------------
# Incomplete project data
# ---------------------------------------------------------------------------


def test_empty_context_does_not_crash_on_seeded_corpus() -> None:
    """The engine must tolerate a project with no inputs supplied."""
    rules = [r.data for r in load_rules()]
    sim = simulate_project(
        rules=rules,
        context=ProjectContext(),
        applicable_jurisdiction_ids=["us", "us-tx"],
        project_types=["transmission_line"],
        jurisdiction_chain=[{"jurisdiction_id": "us", "jurisdiction_level": "federal"}],
        evaluation_date=DATE,
    )
    assert sim.fired == ()  # nothing can fire without inputs


def test_missing_input_is_surfaced() -> None:
    """A rule firing via one branch while another references an absent field."""
    rule = _rule(
        "rule-partial",
        triggers={
            "any": [
                {"field": "project.needed", "operator": "=", "value": True},
                {"field": "project.flag", "operator": "=", "value": True},
            ]
        },
    )
    sim = simulate_project(
        rules=[rule],
        context=ProjectContext.from_namespaces(project={"flag": True}),
        applicable_jurisdiction_ids=["us-tx"],
        project_types=["transmission_line"],
        jurisdiction_chain=_chain(["us-tx"]),
        evaluation_date=DATE,
    )
    assert find_missing_inputs(sim) == {"rule-partial": ["project.needed"]}


# ---------------------------------------------------------------------------
# Ambiguous thresholds
# ---------------------------------------------------------------------------


def test_numeric_threshold_leaves_extracted_from_seeded_rule() -> None:
    """The seeded stormwater rule's acreage thresholds are lifted as leaves."""
    rules = {r.rule_id: r.data for r in load_rules()}
    stormwater = rules["us-tx-tceq-construction-stormwater-cgp"]
    leaves = numeric_threshold_leaves(stormwater["triggers"])
    fields = {(leaf.field, leaf.operator, leaf.value) for leaf in leaves}
    assert ("project.disturbed_acres", ">=", 1.0) in fields
    assert ("derived.common_plan_total_disturbed_acres", ">=", 1.0) in fields


def test_boundary_probe_values_and_operator_semantics() -> None:
    """Boundary probes exercise both sides of a >= 1 threshold deterministically."""
    below, exact, above = boundary_probe_values(1.0)
    assert [below, exact, above] == [0.0, 1.0, 2.0]
    assert apply_operator(">=", below, 1.0) is False
    assert apply_operator(">=", exact, 1.0) is True
    assert apply_operator(">=", above, 1.0) is True


def test_threshold_boundary_fires_exactly_at_limit() -> None:
    """A >= 1 acre rule fires at exactly 1 acre and not at 0."""
    rule = _rule(
        "rule-acre",
        triggers={"field": "project.disturbed_acres", "operator": ">=", "value": 1},
    )
    kwargs = {
        "rules": [rule],
        "applicable_jurisdiction_ids": ["us-tx"],
        "project_types": ["transmission_line"],
        "jurisdiction_chain": _chain(["us-tx"]),
        "evaluation_date": DATE,
    }
    at = simulate_project(
        context=ProjectContext.from_namespaces(project={"disturbed_acres": 1}), **kwargs
    )
    below = simulate_project(
        context=ProjectContext.from_namespaces(project={"disturbed_acres": 0}), **kwargs
    )
    assert [e.rule_id for e in at.fired] == ["rule-acre"]
    assert below.fired == ()


# ---------------------------------------------------------------------------
# Overlapping jurisdictions
# ---------------------------------------------------------------------------


def test_overlapping_jurisdictions_preserve_parent() -> None:
    """Two rules for the same permit at different levels overlap; parent kept."""
    trigger = {"field": "project.flag", "operator": "=", "value": True}
    federal = _rule("rule-fed", triggers=trigger, jid="us", level="federal")
    county = _rule(
        "rule-cnty", triggers=trigger, jid="us-tx-county-test", level="county"
    )
    sim = simulate_project(
        rules=[federal, county],
        context=ProjectContext.from_namespaces(project={"flag": True}),
        applicable_jurisdiction_ids=["us", "us-tx-county-test"],
        project_types=["transmission_line"],
        jurisdiction_chain=_chain(["us", "us-tx-county-test"]),
        evaluation_date=DATE,
    )
    overlaps = overlapping_requirements(sim.resolution)
    assert len(overlaps) == 1
    assert overlaps[0].governing_rule_id == "rule-cnty"  # county is more specific
    assert overlaps[0].contributing_rule_ids == ("rule-fed",)  # parent preserved


# ---------------------------------------------------------------------------
# Conflicting triggers / determinism
# ---------------------------------------------------------------------------


def test_simulation_is_reproducible() -> None:
    """Identical inputs must produce identical fired sets and explanations."""
    rules = [r.data for r in load_rules()]
    kwargs = {
        "rules": rules,
        "context": ProjectContext.from_namespaces(
            project={
                "federal_nexus": True,
                "dredge_or_fill_in_waters": True,
                "stream_crossings_count": 1,
            },
            geometry={"wetlands_present": True, "waters_of_us_present": True},
            derived={"major_federal_action": True, "may_affect_listed_species": True},
        ),
        "applicable_jurisdiction_ids": ["us", "us-tx"],
        "project_types": ["transmission_line"],
        "jurisdiction_chain": [
            {"jurisdiction_id": "us", "jurisdiction_level": "federal"}
        ],
        "evaluation_date": DATE,
    }
    first = simulate_project(**kwargs)
    second = simulate_project(**kwargs)
    assert [e.rule_id for e in first.fired] == [e.rule_id for e in second.fired]
    assert json.dumps(first.explanations, sort_keys=True) == json.dumps(
        second.explanations, sort_keys=True
    )
