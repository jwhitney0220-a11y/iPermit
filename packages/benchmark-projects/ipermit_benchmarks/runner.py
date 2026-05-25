"""Run benchmark projects through the rules engine and compare outputs (T04-02).

Drives the T04-01 simulation engine with each benchmark's inputs and compares
the result against the benchmark's expectations:

- ``expected_outputs.permits``  — exact set of (name, agency).
- ``expected_confidence``       — confidence tier per permit.
- ``expected_known_unknowns``   — set membership (expected is a subset of actual).
- ``expected_advisories``       — set membership (subset).
- ``expected_explanations``     — fired rule_id, jurisdiction level, and a
  keyword-presence check on the trigger summary.

Benchmarks whose ``ruleset_version.content_hash`` starts with ``placeholder:``
are skipped (design-time stubs, not yet runnable). The engine evaluates the
rule snapshot supplied by the caller; see the package README for status caveats.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ipermit_engine import ProjectContext, simulate_project
from ipermit_engine.conflict import precedence_rank

from .loader import Benchmark

_PLACEHOLDER = "placeholder:"
# A canonical jurisdiction_id with exactly two dash-segments (e.g. "us-tx") is a
# state; deeper IDs name a sub-state level in the third segment (T00-08 grammar).
_STATE_ID_SEGMENTS = 2
_LEVEL_TOKENS = (
    "utility-district",
    "drainage-district",
    "river-authority",
    "county",
    "municipality",
    "etj",
    "special",
)
_STOPWORDS = frozenset(
    {
        "the",
        "that",
        "this",
        "with",
        "into",
        "from",
        "they",
        "them",
        "your",
        "commonly",
        "triggers",
        "trigger",
        "requires",
        "require",
        "review",
        "project",
        "permit",
        "must",
        "when",
        "where",
        "which",
        "have",
        "least",
    }
)


@dataclass(frozen=True)
class BenchmarkResult:
    """The outcome of running one benchmark against the engine."""

    benchmark_id: str
    passed: bool
    skipped: bool
    skip_reason: str
    diffs: tuple[str, ...]


def _infer_level(jurisdiction_id: str) -> str:
    """Infer a jurisdiction level from a canonical jurisdiction_id (T00-08 grammar)."""
    if jurisdiction_id == "us" or "-" not in jurisdiction_id:
        return "federal"
    parts = jurisdiction_id.split("-")
    if len(parts) == _STATE_ID_SEGMENTS:
        return "state"
    body = "-".join(parts[2:])
    for token in _LEVEL_TOKENS:
        if body.startswith(token):
            return token.replace("-", "_")
    return "special"


def _jurisdiction_chain(jids: Sequence[str]) -> list[dict[str, str]]:
    """Build the ordered Federal->local jurisdiction chain for explanations."""
    entries = [
        {"jurisdiction_id": j, "jurisdiction_level": _infer_level(j)} for j in jids
    ]
    return sorted(
        entries,
        key=lambda e: (precedence_rank(e["jurisdiction_level"]), e["jurisdiction_id"]),
    )


def _simulate(benchmark: Benchmark, rules: Iterable[Mapping[str, Any]]) -> Any:
    """Build engine inputs from a benchmark and run the simulation."""
    inputs = benchmark.data["project_inputs"]
    namespaces = {k: v for k, v in inputs.get("engine_context", {}).items() if v}
    jids = inputs["applicable_jurisdiction_ids"]
    return simulate_project(
        rules=rules,
        context=ProjectContext.from_namespaces(**namespaces),
        applicable_jurisdiction_ids=jids,
        project_types=[inputs["project_type"]],
        jurisdiction_chain=_jurisdiction_chain(jids),
        evaluation_date=benchmark.data["evaluation_date"],
    )


def _actual_permits(sim: Any) -> set[tuple[str, str]]:
    """Set of (permit name, agency) emitted by the fired rules."""
    return {
        (permit["name"], permit["agency"])
        for rule in sim.fired_rules
        for permit in rule.get("outputs", {}).get("permits", [])
    }


def _permit_tiers(sim: Any) -> dict[str, int]:
    """Map each emitted permit name to its rule's confidence tier."""
    tiers: dict[str, int] = {}
    for rule in sim.fired_rules:
        for permit in rule.get("outputs", {}).get("permits", []):
            tiers[permit["name"]] = rule["confidence_tier"]
    return tiers


def _permit_rule_ids(sim: Any) -> dict[str, set[str]]:
    """Map each emitted permit name to the rule_ids that produced it."""
    mapping: dict[str, set[str]] = {}
    for rule in sim.fired_rules:
        for permit in rule.get("outputs", {}).get("permits", []):
            mapping.setdefault(permit["name"], set()).add(rule["rule_id"])
    return mapping


def _check_permits(benchmark: Benchmark, sim: Any) -> list[str]:
    """Diff expected vs actual permits as an exact (name, agency) set."""
    expected = {
        (p["name"], p["agency"]) for p in benchmark.data["expected_outputs"]["permits"]
    }
    actual = _actual_permits(sim)
    diffs = [
        f"missing expected permit: {n} ({a})" for n, a in sorted(expected - actual)
    ]
    diffs += [
        f"unexpected permit fired: {n} ({a})" for n, a in sorted(actual - expected)
    ]
    return diffs


def _check_confidence(benchmark: Benchmark, sim: Any) -> list[str]:
    """Diff expected vs actual confidence tier per permit."""
    tiers = _permit_tiers(sim)
    diffs: list[str] = []
    for exp in benchmark.data.get("expected_confidence", []):
        actual = tiers.get(exp["permit_name"])
        if actual is None:
            diffs.append(f"no permit '{exp['permit_name']}' to check confidence")
        elif actual != exp["tier"]:
            diffs.append(
                f"permit '{exp['permit_name']}' tier {actual} != expected {exp['tier']}"
            )
    return diffs


def _check_set_membership(
    expected: Iterable[str], actual: set[str], label: str
) -> list[str]:
    """Return a diff for each expected string absent from *actual*."""
    return [
        f"missing expected {label}: {text}" for text in sorted(set(expected) - actual)
    ]


def _keywords_present(summary: str, text: str, threshold: float = 0.5) -> bool:
    """True if at least *threshold* of the summary's significant words appear in text."""
    words = [
        w for w in re.findall(r"[a-z]{4,}", summary.lower()) if w not in _STOPWORDS
    ]
    if not words:
        return True
    hits = sum(1 for w in words if w in text)
    return hits / len(words) >= threshold


def _explanation_text(sim: Any, permit_name: str) -> str:
    """Concatenate the trigger explanations of rules emitting *permit_name*."""
    parts = [
        rule.get("explanations", {}).get("trigger_explanation", "")
        for rule in sim.fired_rules
        if any(
            p["name"] == permit_name for p in rule.get("outputs", {}).get("permits", [])
        )
    ]
    return " ".join(parts).lower()


def _rule_levels(sim: Any, rule_ids: set[str]) -> set[str | None]:
    """Jurisdiction levels of the given fired rule_ids."""
    return {
        rule.get("jurisdiction_level")
        for rule in sim.fired_rules
        if rule["rule_id"] in rule_ids
    }


def _check_one_explanation(
    exp: Mapping[str, Any],
    sim: Any,
    permit_rules: Mapping[str, set[str]],
    fired_ids: set[str],
) -> list[str]:
    """Validate one expected explanation against the simulation output."""
    name = exp["permit_name"]
    rule_ids = permit_rules.get(name)
    if not rule_ids:
        return [f"no fired permit '{name}' for expected explanation"]
    diffs: list[str] = []
    expected_rule = exp.get("expected_rule_id")
    if expected_rule and expected_rule not in fired_ids:
        diffs.append(f"expected rule '{expected_rule}' for '{name}' did not fire")
    levels = exp.get("expected_jurisdiction_levels")
    if levels and not (_rule_levels(sim, rule_ids) & set(levels)):
        diffs.append(f"permit '{name}' jurisdiction level not in expected {levels}")
    if not _keywords_present(exp["trigger_summary"], _explanation_text(sim, name)):
        diffs.append(f"explanation for '{name}' missing expected trigger keywords")
    return diffs


def _check_explanations(benchmark: Benchmark, sim: Any) -> list[str]:
    """Validate every expected explanation."""
    permit_rules = _permit_rule_ids(sim)
    fired_ids = {result.rule_id for result in sim.fired}
    diffs: list[str] = []
    for exp in benchmark.data.get("expected_explanations", []):
        diffs += _check_one_explanation(exp, sim, permit_rules, fired_ids)
    return diffs


def run_benchmark(
    benchmark: Benchmark, rules: Iterable[Mapping[str, Any]]
) -> BenchmarkResult:
    """Run one benchmark against *rules* and return a pass/skip/fail result."""
    content_hash = benchmark.data["ruleset_version"]["content_hash"]
    if content_hash.startswith(_PLACEHOLDER):
        return BenchmarkResult(
            benchmark.benchmark_id,
            False,
            True,
            f"placeholder ruleset ({content_hash})",
            (),
        )
    rules = list(rules)
    sim = _simulate(benchmark, rules)
    known = {item.text for items in sim.known_unknowns.values() for item in items}
    advisories = {a["text"] for expl in sim.explanations for a in expl["advisories"]}
    diffs = (
        _check_permits(benchmark, sim)
        + _check_confidence(benchmark, sim)
        + _check_set_membership(
            benchmark.data.get("expected_known_unknowns", []), known, "known-unknown"
        )
        + _check_set_membership(
            benchmark.data.get("expected_advisories", []), advisories, "advisory"
        )
        + _check_explanations(benchmark, sim)
    )
    return BenchmarkResult(benchmark.benchmark_id, not diffs, False, "", tuple(diffs))


def run_benchmarks(
    benchmarks: Iterable[Benchmark], rules: Iterable[Mapping[str, Any]]
) -> list[BenchmarkResult]:
    """Run every benchmark against *rules* (materialised once)."""
    rules = list(rules)
    return [run_benchmark(b, rules) for b in benchmarks]
