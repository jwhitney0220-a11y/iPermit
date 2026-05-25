#!/usr/bin/env python3
"""Generate Pydantic v2 models and TypeScript types from canonical schemas.

Single source of truth: docs/specs/schemas/*.schema.json (T01-11). Run this
script and commit the generated output; never hand-edit the generated files.

  python scripts/schema/generate.py [--check]

  (no args)  Regenerate all targets in place.
  --check    Regenerate into memory and fail if it differs from what is on
             disk (use this in CI to detect schema/codegen drift).

Outputs:
  packages/shared-schemas/python/ipermit_schemas/<module>.py  (+ __init__.py)
  packages/shared-schemas/typescript/src/<schema>.ts          (+ index.ts)
"""

from __future__ import annotations

import sys
from pathlib import Path

from _common import SCHEMA_NAMES, load_schema, repo_root
from _pydantic_emitter import emit_module as emit_python
from _ts_emitter import emit_module as emit_ts
from _ts_emitter import npx_available

_PY_PKG = "packages/shared-schemas/python/ipermit_schemas"
_TS_SRC = "packages/shared-schemas/typescript/src"


def build_targets() -> dict[str, str]:
    """Return {relative_path: file_content} for every generated file."""
    targets: dict[str, str] = {}
    py_exports: list[tuple[str, str]] = []
    ts_exports: list[str] = []
    for stem, (module, type_name) in SCHEMA_NAMES.items():
        schema = load_schema(stem)
        targets[f"{_PY_PKG}/{module}.py"] = emit_python(schema, type_name)
        targets[f"{_TS_SRC}/{stem}.ts"] = emit_ts(schema, type_name)
        py_exports.append((module, type_name))
        ts_exports.append(stem)
    targets[f"{_PY_PKG}/__init__.py"] = _py_init(py_exports)
    targets[f"{_TS_SRC}/index.ts"] = _ts_index(ts_exports)
    return targets


def _py_init(exports: list[tuple[str, str]]) -> str:
    """Build the package __init__ that re-exports every generated model."""
    from _common import GENERATED_HEADER

    lines = [f'"""{GENERATED_HEADER}"""', "", "from __future__ import annotations", ""]
    for module, type_name in sorted(exports):
        lines.append(f"from .{module} import {type_name}")
    names = ", ".join(repr(t) for _, t in sorted(exports))
    lines += ["", f"__all__ = [{names}]", ""]
    return "\n".join(lines)


def _ts_index(stems: list[str]) -> str:
    """Build the TS barrel that re-exports every generated module."""
    from _common import GENERATED_HEADER

    lines = [f"// {GENERATED_HEADER}", ""]
    for stem in sorted(stems):
        lines.append(f'export * from "./{stem}";')
    return "\n".join(lines) + "\n"


def write_targets(targets: dict[str, str], root: Path) -> None:
    """Write each target to disk, creating parent directories as needed."""
    for rel_path, content in targets.items():
        out = root / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")


def check_targets(targets: dict[str, str], root: Path) -> list[str]:
    """Return the list of paths whose on-disk content differs from generated."""
    drift: list[str] = []
    for rel_path, content in targets.items():
        out = root / rel_path
        if not out.exists() or out.read_text(encoding="utf-8") != content:
            drift.append(rel_path)
    return drift


def main(argv: list[str]) -> int:
    """Entry point: regenerate, or in --check mode report drift."""
    root = repo_root()
    targets = build_targets()
    if "--check" in argv:
        drift = check_targets(targets, root)
        if drift:
            print("Schema codegen drift detected in:\n  " + "\n  ".join(drift))
            return 1
        print(f"OK: {len(targets)} generated files match the schemas.")
        return 0
    write_targets(targets, root)
    emitter = "json2ts" if npx_available() else "built-in fallback"
    print(f"Generated {len(targets)} files (TS via {emitter}) under packages/shared-schemas/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
