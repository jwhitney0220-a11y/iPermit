"""Emit TypeScript types from the canonical JSON Schemas (T01-11).

Primary path uses `json-schema-to-typescript` (json2ts) via `npx`, which is the
tool ADR-0001 names. When npx/node is unavailable we fall back to a minimal,
dependency-free emitter that covers the constructs the iPermit schemas use:
objects, $ref into $defs, oneOf/anyOf unions, enums, const, arrays, nullable
("type": [..., "null"]) and scalars. The fallback is intentionally simple and is
flagged in the generated header so reviewers know it is a degraded emit.

Functions are kept small and single-purpose per AGENTS.md (<60 lines each).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from _common import GENERATED_HEADER, to_pascal_case

# Pinned json2ts version (see _try_json2ts). Bump deliberately + regenerate.
_JSON2TS_VERSION = "15.0.4"

_TS_BANNER = f"// {GENERATED_HEADER}\n"


def emit_module(schema: dict, root_name: str) -> str:
    """Render TypeScript for one schema, preferring json2ts when available."""
    rendered = _try_json2ts(schema, root_name)
    if rendered is not None:
        return _TS_BANNER + "\n" + rendered
    note = (
        "// NOTE: emitted by the minimal built-in fallback (npx json2ts unavailable).\n"
    )
    return _TS_BANNER + note + "\n" + _fallback_module(schema, root_name)


def npx_available() -> bool:
    """True when both npx and node are on PATH."""
    return bool(shutil.which("npx") and shutil.which("node"))


def _try_json2ts(schema: dict, root_name: str) -> str | None:
    """Run json2ts over the schema via stdin; return its TS output or None."""
    if not npx_available():
        return None
    try:
        result = subprocess.run(
            # Pin the json2ts version so generated output is deterministic across
            # local + CI runs (an unpinned npx fetches latest and causes spurious
            # codegen-drift failures). Bump deliberately + regenerate when needed.
            [
                "npx",
                "--yes",
                f"json-schema-to-typescript@{_JSON2TS_VERSION}",
                "--no-additionalProperties",
            ],
            input=json.dumps({**schema, "title": root_name}),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return _strip_tool_banner(result.stdout)


def _strip_tool_banner(text: str) -> str:
    """Drop json2ts's own 'do not modify' banner so ours is authoritative."""
    lines = text.splitlines()
    while lines and (
        lines[0].startswith("/*")
        or lines[0].startswith("*")
        or lines[0].startswith("*/")
        or not lines[0].strip()
    ):
        lines.pop(0)
    return "\n".join(lines).strip() + "\n"


# --- Minimal fallback emitter (used only when npx/node is missing) ---------


def _fallback_module(schema: dict, root_name: str) -> str:
    """Build a TS module of interfaces/aliases from a JSON-Schema subset."""
    blocks: list[str] = []
    for def_name, def_schema in schema.get("$defs", {}).items():
        blocks.append(_fallback_decl(to_pascal_case(def_name), def_schema))
    blocks.append(_fallback_decl(root_name, schema))
    return "\n\n".join(blocks) + "\n"


def _fallback_decl(name: str, node: dict) -> str:
    """Render one interface (object) or type alias (union/enum)."""
    if "oneOf" in node or "anyOf" in node:
        members = node.get("oneOf") or node["anyOf"]
        union = " | ".join(_fallback_type(m) for m in members)
        return f"export type {name} = {union};"
    if node.get("type") == "object" or "properties" in node:
        return _fallback_interface(name, node)
    return f"export type {name} = {_fallback_type(node)};"


def _fallback_interface(name: str, node: dict) -> str:
    """Render an `export interface` from an object schema node."""
    required = set(node.get("required", []))
    lines = [f"export interface {name} {{"]
    for prop, prop_schema in node.get("properties", {}).items():
        opt = "" if prop in required else "?"
        lines.append(f"  {prop}{opt}: {_fallback_type(prop_schema)};")
    lines.append("}")
    return "\n".join(lines)


def _fallback_type(node: dict) -> str:
    """Map a JSON-Schema node to a TS type expression (fallback emitter)."""
    if "$ref" in node:
        return to_pascal_case(node["$ref"].split("/")[-1])
    if "oneOf" in node or "anyOf" in node:
        members = node.get("oneOf") or node["anyOf"]
        return "(" + " | ".join(_fallback_type(m) for m in members) + ")"
    if "const" in node:
        return json.dumps(node["const"])
    if "enum" in node:
        return " | ".join(json.dumps(v) for v in node["enum"])
    return _fallback_scalar(node)


def _fallback_scalar(node: dict) -> str:
    """Map type/array/object scalars to TS, honouring nullable unions."""
    json_type = node.get("type")
    types = json_type if isinstance(json_type, list) else [json_type]
    nullable = "null" in types
    base = next((t for t in types if t and t != "null"), None)
    mapped = _TS_SCALAR.get(base, "unknown")
    if base == "array":
        mapped = f"{_fallback_type(node.get('items', {}))}[]"
    elif base == "object":
        mapped = "Record<string, unknown>"
    return f"{mapped} | null" if nullable else mapped


_TS_SCALAR: dict[Any, str] = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "null": "null",
    None: "unknown",
}
