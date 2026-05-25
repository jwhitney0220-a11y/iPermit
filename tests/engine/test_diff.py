"""Tests for rule diff and change analysis (T04-04)."""

from __future__ import annotations

from typing import Any

from ipermit_engine import (
    ProjectContext,
    diff_rules,
    diff_rulesets,
    output_impact,
)

DATE = "2026-05-25"


def _rule(
    rule_id: str, *, tier: int = 1, status: str = "draft", value: bool = True
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "version": "1.0.0",
        "status": status,
        "jurisdiction_id": "us-tx",
        "jurisdiction_level": "state",
        "applicable_project_types": ["transmission_line"],
        "confidence_tier": tier,
        "provenance": {
            "source_citations": [{"citation_type": "statute", "reference": rule_id}],
            "last_verified": "2026-05-20",
        },
        "triggers": {"field": "project.flag", "operator": "=", "value": value},
        "outputs": {"permits": [{"name": f"Permit {rule_id}", "agency": "Agency"}]},
        "explanations": {"trigger_explanation": f"{rule_id} explanation."},
    }


def _chain() -> list[dict[str, str]]:
    return [{"jurisdiction_id": "us-tx", "jurisdiction_level": "state"}]


# ---------------------------------------------------------------------------
# diff_rules
# ---------------------------------------------------------------------------


def test_diff_rules_detects_scalar_and_struct_changes() -> None:
    old = _rule("rule-a", tier=2, status="draft", value=True)
    new = _rule("rule-a", tier=1, status="effective", value=False)
    new["effective_from"] = "2026-01-01"
    diff = diff_rules(old, new)
    fields = {c.field for c in diff.changed}
    assert {"status", "confidence_tier", "triggers", "effective_from"} <= fields
    assert "status" in diff.summary


def test_diff_rules_no_change() -> None:
    rule = _rule("rule-a")
    diff = diff_rules(rule, dict(rule))
    assert diff.changed == ()
    assert "no load-bearing change" in diff.summary


# ---------------------------------------------------------------------------
# diff_rulesets
# ---------------------------------------------------------------------------


def test_diff_rulesets_added_removed_changed() -> None:
    old = [_rule("rule-a", tier=2), _rule("rule-gone")]
    new = [_rule("rule-a", tier=1), _rule("rule-new")]
    diff = diff_rulesets(old, new)
    assert diff.added == ("rule-new",)
    assert diff.removed == ("rule-gone",)
    assert [d.rule_id for d in diff.changed] == ["rule-a"]
    assert diff.summary == "1 added, 1 removed, 1 changed"


# ---------------------------------------------------------------------------
# output_impact
# ---------------------------------------------------------------------------


def test_output_impact_added_and_removed_permits() -> None:
    old = [_rule("rule-a")]
    new = [_rule("rule-a"), _rule("rule-b")]
    impact = output_impact(
        old,
        new,
        context=ProjectContext.from_namespaces(project={"flag": True}),
        applicable_jurisdiction_ids=["us-tx"],
        project_types=["transmission_line"],
        jurisdiction_chain=_chain(),
        evaluation_date=DATE,
    )
    assert ("Permit rule-b", "Agency") in impact.added_permits
    assert impact.removed_permits == ()
    assert "state" in impact.jurisdiction_levels_affected


def test_output_impact_confidence_change() -> None:
    old = [_rule("rule-a", tier=2)]
    new = [_rule("rule-a", tier=1)]
    impact = output_impact(
        old,
        new,
        context=ProjectContext.from_namespaces(project={"flag": True}),
        applicable_jurisdiction_ids=["us-tx"],
        project_types=["transmission_line"],
        jurisdiction_chain=_chain(),
        evaluation_date=DATE,
    )
    assert impact.confidence_changes == (("Permit rule-a", 2, 1),)
    assert impact.added_permits == ()
    assert impact.removed_permits == ()
