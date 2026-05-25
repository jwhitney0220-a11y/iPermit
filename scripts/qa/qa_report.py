#!/usr/bin/env python3
"""QA/QC analyst report (T04-05).

Internal analyst tooling that surfaces the data an analyst needs to review rule
changes, validate outputs, judge publication readiness, and track unresolved
uncertainties. It is the data layer the future internal web dashboard (T08-02)
will render; today it runs as a CLI that prints a text report (or ``--json``).

It does NOT mutate rules or approve publications — promotion is the analyst
publication workflow (T08-04). This tool only reads and reports.

    python scripts/qa/qa_report.py [--json]
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for _rel in (
    "packages/rule-definitions",
    "packages/benchmark-projects",
    "services/rules-engine",
):
    sys.path.insert(0, str(ROOT / _rel))

from ipermit_benchmarks import load_benchmarks, run_benchmarks  # noqa: E402
from ipermit_rules import load_rules  # noqa: E402

_STALE_THRESHOLD_DAYS = 365
_INFORMATIONAL_TIER = 3


def corpus_stats(rules: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts of the rule corpus by status, confidence tier, and jurisdiction level."""
    return {
        "total": len(rules),
        "by_status": dict(sorted(Counter(r.get("status") for r in rules).items())),
        "by_tier": dict(
            sorted(Counter(r.get("confidence_tier") for r in rules).items())
        ),
        "by_level": dict(
            sorted(Counter(r.get("jurisdiction_level") for r in rules).items())
        ),
    }


def _days_since(last_verified: str | None, today: datetime.date) -> int | None:
    """Whole days between *last_verified* and *today*, or None if unparseable."""
    try:
        return (today - datetime.date.fromisoformat(last_verified)).days
    except (ValueError, TypeError):
        return None


def freshness_flags(
    rules: list[dict[str, Any]],
    today: datetime.date,
    threshold_days: int = _STALE_THRESHOLD_DAYS,
) -> list[dict[str, Any]]:
    """Rules whose last verification is older than *threshold_days* (freshness, T02-07)."""
    flags: list[dict[str, Any]] = []
    for rule in rules:
        last_verified = rule.get("provenance", {}).get("last_verified")
        days = _days_since(last_verified, today)
        if days is not None and days > threshold_days:
            flags.append(
                {
                    "rule_id": rule["rule_id"],
                    "last_verified": last_verified,
                    "days": days,
                }
            )
    return sorted(flags, key=lambda f: (-f["days"], f["rule_id"]))


def uncertainty_flags(rules: list[dict[str, Any]]) -> dict[str, Any]:
    """Track unresolved uncertainty: authored known-unknowns and Tier 3 rules."""
    with_known_unknowns = sorted(r["rule_id"] for r in rules if r.get("known_unknowns"))
    tier_3 = sorted(
        r["rule_id"] for r in rules if r.get("confidence_tier") == _INFORMATIONAL_TIER
    )
    return {
        "rules_with_known_unknowns": with_known_unknowns,
        "informational_tier_rules": tier_3,
    }


def publication_readiness(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per draft rule, the publication-readiness criteria (Human Review Workflow).

    Reports booleans only; a True ``ready`` means provenance is present, NOT that
    a human analyst has approved publication (that is the T08-04 workflow).
    """
    rows: list[dict[str, Any]] = []
    for rule in rules:
        if rule.get("status") != "draft":
            continue
        provenance = rule.get("provenance", {})
        criteria = {
            "has_reviewer": bool(provenance.get("reviewer")),
            "has_citation": bool(provenance.get("source_citations")),
            "has_confidence_tier": rule.get("confidence_tier") in (1, 2, 3),
            "has_explanation": bool(
                rule.get("explanations", {}).get("trigger_explanation")
            ),
        }
        rows.append(
            {"rule_id": rule["rule_id"], "ready": all(criteria.values()), **criteria}
        )
    return sorted(rows, key=lambda r: r["rule_id"])


def regression_summary(results: list[Any]) -> dict[str, Any]:
    """Pass / skip / fail counts (and failing ids) from benchmark results."""
    passed = [r for r in results if r.passed]
    skipped = [r for r in results if r.skipped]
    failed = [r for r in results if not r.passed and not r.skipped]
    return {
        "passed": len(passed),
        "skipped": len(skipped),
        "failed": len(failed),
        "failed_ids": sorted(r.benchmark_id for r in failed),
    }


def build_report(
    rules: list[dict[str, Any]],
    benchmark_results: list[Any],
    today: datetime.date,
) -> dict[str, Any]:
    """Assemble the full QA/QC report from the corpus and benchmark results."""
    return {
        "generated_at": today.isoformat(),
        "corpus": corpus_stats(rules),
        "freshness_flags": freshness_flags(rules, today),
        "uncertainty": uncertainty_flags(rules),
        "publication_readiness": publication_readiness(rules),
        "regression": regression_summary(benchmark_results),
    }


def render_text(report: dict[str, Any]) -> str:
    """Render the report as a compact analyst-facing text block."""
    corpus = report["corpus"]
    ready = sum(1 for r in report["publication_readiness"] if r["ready"])
    regression = report["regression"]
    lines = [
        f"iPermit QA/QC report — {report['generated_at']}",
        f"  corpus: {corpus['total']} rules  status={corpus['by_status']}  "
        f"tier={corpus['by_tier']}",
        f"  jurisdiction levels: {corpus['by_level']}",
        f"  freshness: {len(report['freshness_flags'])} stale rule(s)",
        f"  uncertainty: {len(report['uncertainty']['rules_with_known_unknowns'])} "
        f"with known-unknowns, "
        f"{len(report['uncertainty']['informational_tier_rules'])} Tier 3",
        f"  publication readiness: {ready}/{len(report['publication_readiness'])} "
        f"draft rule(s) meet provenance criteria (human approval still required)",
        f"  regression: {regression['passed']} passed, {regression['skipped']} "
        f"skipped, {regression['failed']} failed",
    ]
    if regression["failed_ids"]:
        lines.append(f"  FAILING benchmarks: {', '.join(regression['failed_ids'])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Build the report from the live corpus and benchmarks; print text or JSON."""
    parser = argparse.ArgumentParser(description="iPermit QA/QC analyst report")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    rules = [rule.data for rule in load_rules()]
    results = run_benchmarks(load_benchmarks(), rules)
    report = build_report(rules, results, datetime.date.today())

    print(json.dumps(report, indent=2) if args.json else render_text(report))
    return 1 if report["regression"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
