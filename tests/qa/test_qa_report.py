"""Tests for the QA/QC analyst report builders (T04-05)."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any

from ipermit_benchmarks import BenchmarkResult

# qa_report is a CLI module under scripts/qa (not an installed package).
_QA_DIR = Path(__file__).resolve().parents[2] / "scripts" / "qa"
sys.path.insert(0, str(_QA_DIR))

import qa_report  # noqa: E402

TODAY = datetime.date(2026, 5, 25)


def _rule(
    rule_id: str,
    *,
    status: str = "draft",
    tier: int = 1,
    level: str = "state",
    last_verified: str = "2026-05-20",
    reviewer: str | None = "analyst",
    known_unknowns: list[str] | None = None,
) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "source_citations": [{"citation_type": "statute", "reference": rule_id}],
        "last_verified": last_verified,
    }
    if reviewer:
        provenance["reviewer"] = reviewer
    rule: dict[str, Any] = {
        "rule_id": rule_id,
        "status": status,
        "confidence_tier": tier,
        "jurisdiction_level": level,
        "provenance": provenance,
        "explanations": {"trigger_explanation": "why"},
    }
    if known_unknowns:
        rule["known_unknowns"] = known_unknowns
    return rule


def test_corpus_stats_counts() -> None:
    rules = [
        _rule("a"),
        _rule("b", tier=3, level="federal"),
        _rule("c", status="effective"),
    ]
    stats = qa_report.corpus_stats(rules)
    assert stats["total"] == 3
    assert stats["by_status"] == {"draft": 2, "effective": 1}
    assert stats["by_tier"] == {1: 2, 3: 1}


def test_freshness_flags_marks_stale_rules() -> None:
    rules = [
        _rule("fresh", last_verified="2026-05-20"),
        _rule("stale", last_verified="2024-01-01"),
    ]
    flags = qa_report.freshness_flags(rules, TODAY)
    assert [f["rule_id"] for f in flags] == ["stale"]
    assert flags[0]["days"] > 365


def test_uncertainty_flags() -> None:
    rules = [_rule("a", known_unknowns=["x"]), _rule("b", tier=3)]
    flags = qa_report.uncertainty_flags(rules)
    assert flags["rules_with_known_unknowns"] == ["a"]
    assert flags["informational_tier_rules"] == ["b"]


def test_publication_readiness_requires_provenance() -> None:
    rules = [
        _rule("ready"),
        _rule("no-reviewer", reviewer=None),
        _rule("effective-skipped", status="effective"),
    ]
    rows = qa_report.publication_readiness(rules)
    by_id = {r["rule_id"]: r for r in rows}
    assert "effective-skipped" not in by_id  # only draft rules are assessed
    assert by_id["ready"]["ready"] is True
    assert by_id["no-reviewer"]["ready"] is False
    assert by_id["no-reviewer"]["has_reviewer"] is False


def test_regression_summary() -> None:
    results = [
        BenchmarkResult("p", True, False, "", ()),
        BenchmarkResult("s", False, True, "placeholder", ()),
        BenchmarkResult("f", False, False, "", ("diff",)),
    ]
    summary = qa_report.regression_summary(results)
    assert summary == {"passed": 1, "skipped": 1, "failed": 1, "failed_ids": ["f"]}


def test_build_report_and_render_text() -> None:
    rules = [_rule("a", known_unknowns=["x"]), _rule("b", tier=3)]
    results = [BenchmarkResult("p", True, False, "", ())]
    report = qa_report.build_report(rules, results, TODAY)
    assert set(report) == {
        "generated_at",
        "corpus",
        "freshness_flags",
        "uncertainty",
        "publication_readiness",
        "regression",
    }
    text = qa_report.render_text(report)
    assert "QA/QC report" in text
    assert "regression: 1 passed" in text
