#!/usr/bin/env python3
"""Validate every rule file in the rules/ tree against the rule-object schema.

Run as a pre-commit hook and in CI (T01-07). Exits non-zero on the first
validation failure. An empty rules/ tree passes (no rules seeded until T02-06).

    python scripts/rules/validate_rules.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "packages" / "rule-definitions")
)

from ipermit_rules import RuleValidationError, load_rules


def main() -> int:
    try:
        rules = load_rules()
    except RuleValidationError as exc:
        print(f"rule validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(rules)} rule file(s) valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
