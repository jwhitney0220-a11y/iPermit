"""Tests for the edge-case testing framework (T04-03)."""

from __future__ import annotations

from typing import Any

from ipermit_engine import ProjectContext
from ipermit_engine.edge_cases import analyze_edge_cases


def _rule(
    rid: str,
    *,
    jid: str = "us-tx-county-x",
    level: str = "county",
    permit: str = "P",
    triggers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": rid,
        "version": "1.0.0",
        "title": rid,
        "permit_name": permit,
        "jurisdiction_level": level,
        "jurisdiction_id": jid,
        "source_agency": "A",
        "confidence_tier": 2,
        "status": "effective",
        "applicable_project_types": ["transmission_line"],
        "triggers": triggers
        or {"field": "project.acreage", "operator": ">=", "value": 1},
        "outputs": {"permits": [{"name": permit, "agency": "A"}]},
    }


_PT = ["transmission_line"]


def test_overlapping_jurisdictions_flagged() -> None:
    ctx = ProjectContext({"project.acreage": 10})
    rules = [
        _rule("r-state", jid="us-tx", level="state", permit="Water Quality Cert"),
        _rule(
            "r-county",
            jid="us-tx-county-x",
            level="county",
            permit="Water Quality Cert",
        ),
    ]
    report = analyze_edge_cases(rules, ctx, ["us-tx", "us-tx-county-x"], _PT)
    assert len(report.overlapping_jurisdictions) == 1


def test_incomplete_data_flagged() -> None:
    ctx = ProjectContext({"project.acreage": 10})
    rule = _rule(
        "r-miss", triggers={"field": "project.unknown_x", "operator": "exists"}
    )
    report = analyze_edge_cases([rule], ctx, ["us-tx-county-x"], _PT)
    assert [f.rule_id for f in report.incomplete_data] == ["r-miss"]
    assert "project.unknown_x" in report.incomplete_data[0].missing_fields


def test_conflicting_triggers_flagged() -> None:
    ctx = ProjectContext({"project.acreage": 10})
    rules = [
        _rule(
            "a",
            permit="PA",
            triggers={"field": "project.acreage", "operator": ">=", "value": 10},
        ),
        _rule(
            "b",
            permit="PB",
            triggers={"field": "project.acreage", "operator": "<", "value": 10},
        ),
    ]
    report = analyze_edge_cases(rules, ctx, ["us-tx-county-x"], _PT)
    assert len(report.conflicting_triggers) >= 1


def test_ambiguous_threshold_flagged() -> None:
    # acreage exactly equals the strict-comparison boundary.
    ctx = ProjectContext({"project.acreage": 10})
    rule = _rule(
        "r1", triggers={"field": "project.acreage", "operator": ">", "value": 10}
    )
    report = analyze_edge_cases([rule], ctx, ["us-tx-county-x"], _PT)
    assert len(report.ambiguous_thresholds) >= 1


def test_clean_ruleset_no_findings() -> None:
    ctx = ProjectContext({"project.acreage": 50})
    report = analyze_edge_cases([_rule("solo")], ctx, ["us-tx-county-x"], _PT)
    assert report.overlapping_jurisdictions == ()
    assert report.incomplete_data == ()


def test_deterministic() -> None:
    ctx = ProjectContext({"project.acreage": 10})
    rules = [
        _rule("r-state", jid="us-tx", level="state", permit="Cert"),
        _rule("r-county", jid="us-tx-county-x", level="county", permit="Cert"),
    ]
    a = analyze_edge_cases(rules, ctx, ["us-tx", "us-tx-county-x"], _PT)
    b = analyze_edge_cases(rules, ctx, ["us-tx", "us-tx-county-x"], _PT)
    assert a == b
