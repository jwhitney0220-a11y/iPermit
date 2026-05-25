#!/usr/bin/env python3
"""Fail if any Python function or method body exceeds the 60-line limit.

The 60-line rule is iPermit's headline engineering constraint (see AGENTS.md
"Engineering Standards" and docs/engineering-handbook/01-engineering-standards.md
§3). This checker enforces it deterministically over the files passed on the
command line so it can run as a pre-commit hook and in CI (T01-02).

What counts toward the limit (matching the handbook):
- Every physical line of the function BODY: code, comments, and blank lines.
- The signature line(s) and any decorators do NOT count.

We measure the body span as `last_line_of_body - first_line_of_body + 1`, where
the first body line is the line after the signature. This is intentionally
simple and conservative; it never undercounts a sprawling function.

Usage:
    python scripts/checks/check_function_length.py path/to/file.py [more.py ...]

Exits non-zero on the first run that finds any violation, printing one line per
violation in the form:  path:line function_name (N lines)
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass

MAX_BODY_LINES = 60

FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class Violation:
    """A single function whose body exceeds the line limit."""

    path: str
    line: int
    name: str
    body_lines: int

    def format(self) -> str:
        return f"{self.path}:{self.line} {self.name} ({self.body_lines} lines)"


def body_line_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count physical lines in a function body, excluding signature/decorators.

    The body starts on the line after the signature ends and runs to the last
    line of the final statement. Comments and blank lines inside that span are
    included because they sit between real source lines.
    """
    first_stmt = node.body[0]
    body_start = first_stmt.lineno
    body_end = max(_node_end_line(child) for child in node.body)
    return body_end - body_start + 1


def _node_end_line(node: ast.AST) -> int:
    """Return the last physical line a node occupies (best-effort)."""
    end = getattr(node, "end_lineno", None)
    if end is not None:
        return end
    return getattr(node, "lineno", 0)


def find_violations(path: str, source: str) -> list[Violation]:
    """Parse `source` and return every function whose body is too long."""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        print(f"{path}: could not parse ({exc})", file=sys.stderr)
        return []

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, FUNC_NODES) or not node.body:
            continue
        count = body_line_count(node)
        if count > MAX_BODY_LINES:
            violations.append(Violation(path, node.lineno, node.name, count))
    return violations


def check_paths(paths: list[str]) -> list[Violation]:
    """Run the check across every given path, collecting all violations."""
    all_violations: list[Violation] = []
    for path in paths:
        try:
            source = _read(path)
        except OSError as exc:
            print(f"{path}: could not read ({exc})", file=sys.stderr)
            continue
        all_violations.extend(find_violations(path, source))
    return all_violations


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def main(argv: list[str]) -> int:
    """CLI entry point. Returns 0 when clean, 1 when any function is too long."""
    paths = argv[1:]
    if not paths:
        print("usage: check_function_length.py <file.py> [...]", file=sys.stderr)
        return 0

    violations = check_paths(paths)
    if not violations:
        return 0

    print(f"Function-length check failed (limit {MAX_BODY_LINES} body lines):")
    for violation in violations:
        print(f"  {violation.format()}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
