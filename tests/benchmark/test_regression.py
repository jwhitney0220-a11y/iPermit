"""Tests for the benchmark regression framework (T04-02).

Loads the real benchmark corpus and the seeded rule snapshot, runs every
benchmark through the simulation engine, and asserts none fail. Also covers the
placeholder skip gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ipermit_benchmarks import Benchmark, load_benchmarks, run_benchmark, run_benchmarks
from ipermit_rules import load_rules


@pytest.fixture(scope="module")
def rules() -> list[dict]:
    """The current rule snapshot (all statuses) as plain dicts."""
    return [rule.data for rule in load_rules()]


@pytest.fixture(scope="module")
def benchmarks() -> list[Benchmark]:
    return load_benchmarks()


def test_benchmark_corpus_loads_and_validates(benchmarks: list[Benchmark]) -> None:
    """At least the three authored seed benchmarks load and schema-validate."""
    assert len(benchmarks) >= 3
    ids = {b.benchmark_id for b in benchmarks}
    assert "federal-nexus-transmission-stream-crossing" in ids


def test_no_benchmark_fails(benchmarks: list[Benchmark], rules: list[dict]) -> None:
    """Every benchmark must pass or skip — never fail — against the snapshot."""
    results = run_benchmarks(benchmarks, rules)
    failed = [
        (r.benchmark_id, r.diffs) for r in results if not r.passed and not r.skipped
    ]
    assert not failed, f"benchmark regressions: {failed}"


def test_at_least_three_benchmarks_pass(
    benchmarks: list[Benchmark], rules: list[dict]
) -> None:
    """The authored real benchmarks should actually run (not all skipped)."""
    results = run_benchmarks(benchmarks, rules)
    assert sum(1 for r in results if r.passed) >= 3


def test_federal_nexus_benchmark_fires_five_permits(
    benchmarks: list[Benchmark], rules: list[dict]
) -> None:
    """Spot-check the federal-nexus benchmark passes with its expected permits."""
    bench = next(
        b
        for b in benchmarks
        if b.benchmark_id == "federal-nexus-transmission-stream-crossing"
    )
    result = run_benchmark(bench, rules)
    assert result.passed, result.diffs
    assert len(bench.data["expected_outputs"]["permits"]) == 5


def test_placeholder_benchmark_is_skipped(rules: list[dict]) -> None:
    """A placeholder ruleset hash must skip, not fail."""
    stub = Benchmark(
        benchmark_id="stub-placeholder",
        category="simple_linear",
        path=Path("stub.yaml"),
        data={"ruleset_version": {"content_hash": "placeholder:design-time"}},
    )
    result = run_benchmark(stub, rules)
    assert result.skipped is True
    assert result.passed is False
