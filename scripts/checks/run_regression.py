#!/usr/bin/env python3
"""Run the benchmark regression suite (T04-02).

Loads the rule snapshot and the benchmark corpus, runs every benchmark through
the simulation engine, prints a pass/skip/fail summary, and exits non-zero on
any real failure. Placeholder (design-time) benchmarks are skipped, not failed.

    python scripts/checks/run_regression.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _rel in (
    "packages/rule-definitions",
    "packages/benchmark-projects",
    "services/rules-engine",
):
    sys.path.insert(0, str(ROOT / _rel))

from ipermit_benchmarks import load_benchmarks, run_benchmarks  # noqa: E402
from ipermit_rules import load_rules  # noqa: E402


def main() -> int:
    rules = [rule.data for rule in load_rules()]
    results = run_benchmarks(load_benchmarks(), rules)
    passed = [r for r in results if r.passed]
    skipped = [r for r in results if r.skipped]
    failed = [r for r in results if not r.passed and not r.skipped]

    for result in failed:
        print(f"FAIL {result.benchmark_id}:")
        for diff in result.diffs:
            print(f"    - {diff}")
    for result in skipped:
        print(f"SKIP {result.benchmark_id}: {result.skip_reason}")
    for result in passed:
        print(f"PASS {result.benchmark_id}")

    print(
        f"\nregression: {len(passed)} passed, {len(skipped)} skipped, "
        f"{len(failed)} failed (of {len(results)})"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
