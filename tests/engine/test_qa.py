"""Tests for the QA/QC aggregation layer (T04-05)."""

from __future__ import annotations

from typing import Any

from ipermit_engine import ProjectContext, evaluate_ruleset
from ipermit_engine.qa import build_qa_report


def _rule(
    rid: str,
    *,
    tier: int = 2,
    status: str = "effective",
    reviewer: str | None = "jw",
    provenance: bool = True,
    advisories: bool = True,
) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "rule_id": rid,
        "version": "1.0.0",
        "title": rid,
        "permit_name": "P",
        "jurisdiction_level": "county",
        "jurisdiction_id": "us-tx-county-x",
        "source_agency": "A",
        "confidence_tier": tier,
        "status": status,
        "applicable_project_types": ["transmission_line"],
        "triggers": {"field": "project.acreage", "operator": ">=", "value": 1},
        "outputs": {"permits": [{"name": "P", "agency": "A"}]},
        "explanations": {"trigger_explanation": "x"},
    }
    if advisories:
        rule["advisories"] = ["This is an advisory identification."]
    if provenance:
        prov: dict[str, Any] = {
            "source_citations": [{"citation_type": "statute", "reference": "x"}],
            "last_verified": "2026-01-01",
        }
        if reviewer:
            prov["reviewer"] = reviewer
        rule["provenance"] = prov
    return rule


def _evaluate(rules: list[dict[str, Any]]):
    ctx = ProjectContext({"project.acreage": 5})
    return list(evaluate_ruleset(rules, ctx, ["us-tx-county-x"], ["transmission_line"]))


def test_tier_counts() -> None:
    rules = [_rule("r1", tier=1), _rule("r2", tier=2), _rule("r3", tier=3)]
    report = build_qa_report(rules, _evaluate(rules))
    assert report.tier_counts.tier_1 == 1
    assert report.tier_counts.tier_2 == 1
    assert report.tier_counts.tier_3 == 1


def test_pending_review_lists_unpublished() -> None:
    rules = [_rule("r-draft", status="draft"), _rule("r-eff", status="effective")]
    report = build_qa_report(rules, _evaluate(rules))
    assert "r-draft" in report.pending_review_rule_ids
    assert "r-eff" not in report.pending_review_rule_ids


def test_publication_gate_flags_missing_provenance_and_reviewer() -> None:
    rules = [_rule("r-bad", provenance=False, advisories=False)]
    report = build_qa_report(rules, _evaluate(rules))
    gate = next(g for g in report.publication_gates if g.rule_id == "r-bad")
    assert gate.provenance_present is False
    assert gate.reviewer_present is False
    assert gate.advisory_language_present is False


def test_publication_gate_all_pass_for_complete_rule() -> None:
    rules = [_rule("r-good")]
    report = build_qa_report(rules, _evaluate(rules))
    gate = next(g for g in report.publication_gates if g.rule_id == "r-good")
    assert gate.provenance_present
    assert gate.reviewer_present
    assert gate.confidence_tier_assigned
    assert gate.advisory_language_present


def test_tier3_surfaces_unresolved_unknown() -> None:
    rules = [_rule("r-t3", tier=3)]
    report = build_qa_report(rules, _evaluate(rules))
    assert len(report.unresolved_unknowns) >= 1


def test_deterministic() -> None:
    rules = [_rule("b"), _rule("a", tier=3)]
    evals = _evaluate(rules)
    assert build_qa_report(rules, evals) == build_qa_report(rules, evals)
