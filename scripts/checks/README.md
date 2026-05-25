# scripts/checks/

Custom repository checks that enforce iPermit's engineering standards. These run
locally via pre-commit (`.pre-commit-config.yaml`) and will be wired into CI
under T01-07.

## `check_function_length.py`

Enforces the headline engineering constraint from
[`AGENTS.md`](../../AGENTS.md) "Engineering Standards" and
[`docs/engineering-handbook/01-engineering-standards.md`](../../docs/engineering-handbook/01-engineering-standards.md)
§3:

> **All code functions MUST remain under 60 lines.**

### What it measures

The function/method **body** — every physical line from the first statement to
the last, including comments and blank lines. The signature line(s) and any
decorators do **not** count, matching the handbook definition. A function with a
61-line body fails; a 60-line body passes.

The implementation is AST-based (`ast.parse` + `ast.walk`), so it never depends
on regexes or brace matching and works for both `def` and `async def`, including
nested functions and methods.

### Usage

```bash
# Check specific files
python scripts/checks/check_function_length.py services/rules-engine/foo.py

# Check everything tracked (example)
git ls-files '*.py' | xargs python scripts/checks/check_function_length.py
```

Exit codes:

- `0` — no violations (or no paths supplied).
- `1` — at least one function body exceeds 60 lines.

Violations print one per line as:

```
path:line function_name (N lines)
```

### When this fires

Do not bump the limit. Split the function — see the handbook §3 "What to do when
a function approaches 60 lines". Extract a helper with a verb-noun name, or fix
the underlying data structure. A one-line `_helper()` shoved out just to pass the
check is explicitly an anti-pattern.
