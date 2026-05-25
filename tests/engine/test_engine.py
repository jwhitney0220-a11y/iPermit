"""Pipeline tests for the rule evaluation engine (T03-02).

Exercises the spec §8 applicability order, short-circuiting, and deterministic
output against the canonical CWA Section 404 example rule
(docs/specs/examples/rule-object-example.json) plus small synthetic rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from ipermit_engine import (
    DecisionStep,
    ProjectContext,
    evaluate_rule,
    evaluate_ruleset,
)

# The example rule's jurisdiction and one of its project types.
CWA_JURISDICTION = "us-federal"
CWA_TYPE = "transmission_line"


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "specs" / "examples").is_dir():
            return parent
    raise FileNotFoundError("repo root not found")


@pytest.fixture(scope="module")
def cwa_rule() -> dict[str, Any]:
    """Load the canonical CWA-404 example rule object (T00-01)."""
    path = _repo_root() / "docs/specs/examples/rule-object-example.json"
    return json.loads(path.read_text())


def _firing_context() -> ProjectContext:
    """A context that SHOULD fire CWA-404: federal nexus + a stream crossing."""
    return ProjectContext(
        {
            "project.federal_nexus": True,
            "project.stream_crossings_count": 1,
            "project.has_wetlands": False,
        }
    )


# ---------------------------------------------------------------------------
# Firing path
# ---------------------------------------------------------------------------


def test_cwa_fires_with_federal_nexus_and_stream(cwa_rule: dict[str, Any]) -> None:
    result = evaluate_rule(cwa_rule, _firing_context(), [CWA_JURISDICTION], [CWA_TYPE])
    assert result.fired is True
    assert result.decided_by is DecisionStep.FIRED
    assert result.rule_id == "us-federal-cwa-section-404-usace-permit"


def test_cwa_fired_evaluated_tree_is_correct(cwa_rule: dict[str, Any]) -> None:
    result = evaluate_rule(cwa_rule, _firing_context(), [CWA_JURISDICTION], [CWA_TYPE])
    tree = result.evaluated_triggers
    assert tree is not None
    assert list(tree) == ["all", "matched"]
    assert tree["matched"] is True
    # First all-child: project.federal_nexus = true (matched).
    nexus_leaf = tree["all"][0]
    assert nexus_leaf == {
        "field": "project.federal_nexus",
        "operator": "=",
        "expected_value": True,
        "actual_value": True,
        "matched": True,
    }
    # Second all-child: an `any` whose first branch (stream crossings) matched,
    # and whose other two branches did not.
    any_node = tree["all"][1]
    assert list(any_node) == ["any", "matched"]
    assert any_node["matched"] is True
    branches = any_node["any"]
    assert branches[0]["field"] == "project.stream_crossings_count"
    assert branches[0]["matched"] is True
    assert branches[1]["field"] == "project.has_wetlands"
    assert branches[1]["matched"] is False
    assert branches[2]["field"] == "geometry.intersects_usace_district"
    assert branches[2]["matched"] is False  # geometry not supplied -> exists False


def test_cwa_fires_via_geometry_overlay(cwa_rule: dict[str, Any]) -> None:
    # Step 5 (spatial overlays): geometry.* is read as an ordinary context value.
    ctx = ProjectContext(
        {
            "project.federal_nexus": True,
            "project.stream_crossings_count": 0,
            "project.has_wetlands": False,
            "geometry.intersects_usace_district": ["swg"],
        }
    )
    result = evaluate_rule(cwa_rule, ctx, [CWA_JURISDICTION], [CWA_TYPE])
    assert result.fired is True
    overlay_leaf = result.evaluated_triggers["all"][1]["any"][2]
    assert overlay_leaf["field"] == "geometry.intersects_usace_district"
    assert overlay_leaf["matched"] is True


# ---------------------------------------------------------------------------
# Non-firing / short-circuit paths
# ---------------------------------------------------------------------------


def test_cwa_does_not_fire_without_federal_nexus(cwa_rule: dict[str, Any]) -> None:
    ctx = ProjectContext(
        {
            "project.federal_nexus": False,
            "project.stream_crossings_count": 1,
        }
    )
    result = evaluate_rule(cwa_rule, ctx, [CWA_JURISDICTION], [CWA_TYPE])
    assert result.fired is False
    assert result.decided_by is DecisionStep.TRIGGERS
    # The trigger tree is still produced (failure was at step 4).
    assert result.evaluated_triggers is not None
    assert result.evaluated_triggers["matched"] is False
    assert result.evaluated_triggers["all"][0]["matched"] is False


def test_cwa_short_circuits_on_jurisdiction(cwa_rule: dict[str, Any]) -> None:
    # Project's chain does not include us-federal: step 1 eliminates the rule
    # before triggers are ever evaluated.
    result = evaluate_rule(cwa_rule, _firing_context(), ["tx-state"], [CWA_TYPE])
    assert result.fired is False
    assert result.decided_by is DecisionStep.JURISDICTION
    assert result.evaluated_triggers is None  # short-circuited before step 4


def test_cwa_short_circuits_on_project_type(cwa_rule: dict[str, Any]) -> None:
    # substation is not in applicable_project_types: step 3 eliminates the rule.
    result = evaluate_rule(
        cwa_rule, _firing_context(), [CWA_JURISDICTION], ["substation"]
    )
    assert result.fired is False
    assert result.decided_by is DecisionStep.PROJECT_TYPE
    assert result.evaluated_triggers is None


def test_jurisdiction_checked_before_project_type(cwa_rule: dict[str, Any]) -> None:
    # Both jurisdiction and project type are wrong; step 1 wins (ordering proof).
    result = evaluate_rule(cwa_rule, _firing_context(), ["tx-state"], ["substation"])
    assert result.decided_by is DecisionStep.JURISDICTION


# ---------------------------------------------------------------------------
# Ruleset evaluation + determinism
# ---------------------------------------------------------------------------


def _mini_rule(rule_id: str, fires: bool) -> dict[str, Any]:
    """A tiny synthetic rule whose single leaf fires when *fires* is desired."""
    return {
        "rule_id": rule_id,
        "jurisdiction_id": "us-federal",
        "applicable_project_types": ["linear_general"],
        "triggers": {
            "field": "project.flag",
            "operator": "=",
            "value": bool(fires),
        },
    }


def test_ruleset_returns_only_fired_rules() -> None:
    rules = [_mini_rule("rule-fires", True), _mini_rule("rule-quiet", False)]
    ctx = ProjectContext({"project.flag": True})
    results = evaluate_ruleset(rules, ctx, ["us-federal"], ["linear_general"])
    assert [r.rule_id for r in results] == ["rule-fires"]
    assert all(r.fired for r in results)


def test_ruleset_sorted_by_rule_id_deterministic() -> None:
    rules = [
        _mini_rule("zzz-rule", True),
        _mini_rule("aaa-rule", True),
        _mini_rule("mmm-rule", True),
    ]
    ctx = ProjectContext({"project.flag": True})
    results = evaluate_ruleset(rules, ctx, ["us-federal"], ["linear_general"])
    ids = [r.rule_id for r in results]
    assert ids == ["aaa-rule", "mmm-rule", "zzz-rule"]
    # Re-running yields identical ordering (determinism contract, T00-05 §6).
    again = evaluate_ruleset(rules, ctx, ["us-federal"], ["linear_general"])
    assert [r.rule_id for r in again] == ids


def test_ruleset_accepts_non_reiterable_inputs() -> None:
    # Generators for the criteria must not be exhausted between rules.
    rules = [_mini_rule("a", True), _mini_rule("b", True)]
    ctx = ProjectContext({"project.flag": True})
    results = evaluate_ruleset(
        rules,
        ctx,
        (j for j in ["us-federal"]),
        (t for t in ["linear_general"]),
    )
    assert [r.rule_id for r in results] == ["a", "b"]


def test_ruleset_empty_when_nothing_fires() -> None:
    rules = [_mini_rule("a", False), _mini_rule("b", False)]
    ctx = ProjectContext({"project.flag": True})
    results = evaluate_ruleset(rules, ctx, ["us-federal"], ["linear_general"])
    assert results == []
