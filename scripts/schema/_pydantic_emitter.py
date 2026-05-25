"""Emit Pydantic v2 models from a JSON Schema (draft 2020-12 subset).

Supports the constructs the iPermit canonical schemas actually use: objects with
properties, $ref into $defs, oneOf unions (the recursive condition trees),
enums, const, arrays, nullable ("type": [..., "null"]) and string formats.
Anything outside that subset degrades to a permissive type with a TODO note.

Functions are kept small and single-purpose per AGENTS.md (<60 lines each).
"""

from __future__ import annotations

import keyword
from typing import Any

from _common import GENERATED_HEADER, to_pascal_case

_FORMAT_HINTS = {"date": "date string (YYYY-MM-DD)", "uri": "URI", "email": "email"}


def emit_module(schema: dict, root_name: str) -> str:
    """Render a full Python module string for one schema."""
    ctx = _Emitter(root_name)
    ctx.collect_defs(schema.get("$defs", {}))
    ctx.add_model(root_name, schema)
    return ctx.render()


class _Emitter:
    """Accumulates model class definitions in dependency order."""

    def __init__(self, root_name: str) -> None:
        self.root_name = root_name
        self.blocks: list[str] = []
        self.names: set[str] = set()
        self.uses_any = False

    def collect_defs(self, defs: dict[str, Any]) -> None:
        """Register object $defs first, then union aliases that reference them.

        Two passes keep generated module-level Union aliases valid: their member
        classes must already be defined when the alias line executes.
        """
        unions = []
        for def_name, def_schema in defs.items():
            cls = to_pascal_case(def_name)
            if "oneOf" in def_schema or "anyOf" in def_schema:
                unions.append((cls, def_schema))
            else:
                self.add_model(cls, def_schema)
        for cls, def_schema in unions:
            self._add_union_alias(cls, def_schema)

    def _add_union_alias(self, cls: str, def_schema: dict) -> None:
        members = def_schema.get("oneOf") or def_schema.get("anyOf") or []
        types = [self._type_for(m) for m in members]
        self.blocks.append(f"{cls} = Union[{', '.join(types)}]")
        self.names.add(cls)

    def add_model(self, cls: str, schema: dict) -> None:
        """Emit a BaseModel subclass for an object schema."""
        if cls in self.names:
            return
        self.names.add(cls)
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines = [f"class {cls}(BaseModel):"]
        doc = schema.get("description") or schema.get("title")
        if doc:
            lines.append(f'    """{_one_line(doc)}"""')
        lines.append(
            "    model_config = ConfigDict(extra='forbid', populate_by_name=True)"
        )
        if not props:
            lines.append("    pass" if not doc else "")
        for prop, prop_schema in props.items():
            lines.append(self._field_line(prop, prop_schema, prop in required))
        self.blocks.append("\n".join(filter(None, lines)))

    def _field_line(self, name: str, prop: dict, is_required: bool) -> str:
        py_type = self._type_for(prop)
        meta = _field_metadata(prop)
        if not is_required:
            py_type = f"Optional[{py_type}]"
        safe_name = f"{name}_" if keyword.iskeyword(name) else name
        if safe_name != name:
            meta = f", alias={name!r}{meta}"
        default = "..." if is_required else "None"
        field = f"Field({default}{meta})" if meta or not is_required else "..."
        if field == "...":
            return f"    {safe_name}: {py_type}"
        return f"    {safe_name}: {py_type} = {field}"

    def _type_for(self, prop: dict) -> str:
        """Map a JSON-Schema node to a Python type expression."""
        if "$ref" in prop:
            return to_pascal_case(prop["$ref"].split("/")[-1])
        if "oneOf" in prop or "anyOf" in prop:
            members = prop.get("oneOf") or prop["anyOf"]
            return f"Union[{', '.join(self._type_for(m) for m in members)}]"
        if "const" in prop:
            return f"Literal[{_literal(prop['const'])}]"
        if "enum" in prop:
            return self._enum_type(prop["enum"])
        return self._type_from_json_type(prop)

    def _enum_type(self, values: list) -> str:
        rendered = ", ".join(_literal(v) for v in values)
        return f"Literal[{rendered}]"

    def _type_from_json_type(self, prop: dict) -> str:
        json_type = prop.get("type")
        nullable = isinstance(json_type, list) and "null" in json_type
        base = _primary_type(json_type)
        if base == "array":
            inner = self._type_for(prop.get("items", {}))
            mapped = f"List[{inner}]"
        elif base == "object":
            mapped = self._anon_object(prop)
        else:
            mapped = _SCALAR.get(base, self._fallback())
        return f"Optional[{mapped}]" if nullable else mapped

    def _anon_object(self, prop: dict) -> str:
        """Objects with no $ref become Dict[str, Any] (permissive map)."""
        if "properties" not in prop:
            self.uses_any = True
            return "Dict[str, Any]"
        self.uses_any = True
        return "Dict[str, Any]"

    def _fallback(self) -> str:
        self.uses_any = True
        return "Any"

    def render(self) -> str:
        """Assemble imports + class blocks into a module string."""
        header = _module_header()
        body = "\n\n\n".join(self.blocks)
        return f"{header}\n\n{body}\n"


_SCALAR = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "null": "None",
    None: "Any",
}


def _primary_type(json_type: Any) -> Any:
    if isinstance(json_type, list):
        non_null = [t for t in json_type if t != "null"]
        return non_null[0] if non_null else "null"
    return json_type


def _literal(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def _field_metadata(prop: dict) -> str:
    """Build Field(...) keyword args from validation/description keywords."""
    args: list[str] = []
    desc = prop.get("description")
    if desc:
        args.append(f"description={_one_line(desc)!r}")
    fmt = prop.get("format")
    if fmt in _FORMAT_HINTS:
        args.append(f"json_schema_extra={{'format': {fmt!r}}}")
    for key, kw in (("minLength", "min_length"), ("maxLength", "max_length")):
        if key in prop:
            args.append(f"{kw}={prop[key]}")
    for key, kw in (("minimum", "ge"), ("maximum", "le")):
        if key in prop:
            args.append(f"{kw}={prop[key]}")
    if "pattern" in prop:
        args.append(f"pattern={prop['pattern']!r}")
    return (", " + ", ".join(args)) if args else ""


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _module_header() -> str:
    return (
        f'"""{GENERATED_HEADER}"""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import Any, Dict, List, Literal, Optional, Union\n\n"
        "from pydantic import BaseModel, ConfigDict, Field"
    )
