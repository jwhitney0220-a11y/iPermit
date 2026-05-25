"""Tests for rule diff & change analysis (T04-04)."""

from __future__ import annotations

from typing import Any

from ipermit_engine.rule_diff import diff_rules, summarize_diff


def _rule(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "rule_id": "r1",
        "version": "1.0.0",
        "title": "Title",
        "permit_name": "P",
        "jurisdiction_level": "county",
        "jurisdiction_id": "us-tx-county-x",
        "source_agency": "A",
        "confidence_tier": 2,
        "status": "effective",
        "applicable_project_types": ["transmission_line"],
        "triggers": {"field": "project.acreage", "operator": ">=", "value": 1},
        "outputs": {"permits": [{"name": "P", "agency": "A"}]},
        "provenance": {
            "source_citations": [
                {"citation_type": "statute", "reference": "33 USC 1344"}
            ],
            "last_verified": "2026-01-01",
        },
    }
    base.update(over)
    return base


def test_no_change_is_empty_diff() -> None:
    diff = diff_rules(_rule(), _rule())
    assert diff.field_changes == ()
    assert diff.trigger_changes == ()
    assert diff.output_changes == ()


def test_field_change_detected() -> None:
    diff = diff_rules(_rule(title="Old"), _rule(title="New", version="1.1.0"))
    names = {c.field_name for c in diff.field_changes}
    assert "title" in names


def test_trigger_change_detected() -> None:
    old = _rule()
    new = _rule(triggers={"field": "project.acreage", "operator": ">=", "value": 5})
    diff = diff_rules(old, new)
    assert len(diff.trigger_changes) >= 1


def test_output_change_detected() -> None:
    old = _rule()
    new = _rule(
        outputs={
            "permits": [{"name": "P", "agency": "A"}, {"name": "Extra", "agency": "B"}]
        }
    )
    diff = diff_rules(old, new)
    assert len(diff.output_changes) >= 1


def test_jurisdiction_change_detected() -> None:
    diff = diff_rules(_rule(), _rule(jurisdiction_id="us-tx-county-y"))
    names = {c.field_name for c in diff.jurisdiction_changes} | {
        c.field_name for c in diff.field_changes
    }
    assert "jurisdiction_id" in names


def test_summarize_returns_text() -> None:
    diff = diff_rules(_rule(title="Old"), _rule(title="New"))
    summary = summarize_diff(diff)
    assert isinstance(summary, str)
    assert summary


def test_diff_deterministic() -> None:
    old, new = _rule(title="Old"), _rule(title="New", confidence_tier=3)
    assert diff_rules(old, new) == diff_rules(old, new)
