#!/usr/bin/env python3
"""Validate the canonical JSON Schemas and that the EPIC-00 examples conform.

Two checks, both wired into CI (T01-07):
  1. Every docs/specs/schemas/*.schema.json is a valid draft 2020-12 schema.
  2. Every example under docs/specs/examples/ validates against its schema.

    python scripts/checks/validate_schemas.py

Exits non-zero on the first failure.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "docs" / "specs" / "schemas"
EX_DIR = ROOT / "docs" / "specs" / "examples"

# example path (relative to EX_DIR) -> schema filename. A glob value expands.
EXAMPLE_MAP = {
    "rule-object-example.json": "rule-object.schema.json",
    "permit-explanation-example.json": "permit-explanation.schema.json",
    "jurisdiction-record-examples.json": "jurisdiction-record.schema.json",
    "spatial-detection-example.json": "spatial-detection.schema.json",
    "benchmarks/*.yaml": "benchmark-project.schema.json",
}


def _isoformat(obj):
    """Render YAML date/datetime as an ISO string (JSON is the canonical form)."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    raise TypeError(f"not JSON-serializable: {type(obj).__name__}")


def _load(path: Path):
    """Parse a JSON or YAML document, normalizing YAML dates to ISO strings."""
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(path.read_text())
        return json.loads(json.dumps(data, default=_isoformat))
    return json.loads(path.read_text())


def check_schemas() -> list[str]:
    """Return a list of error strings for any invalid schema file."""
    errors: list[str] = []
    for schema_path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        try:
            jsonschema.Draft202012Validator.check_schema(
                json.loads(schema_path.read_text())
            )
        except jsonschema.exceptions.SchemaError as exc:
            errors.append(f"{schema_path.name}: invalid schema: {exc.message}")
    return errors


def _records(doc) -> list:
    """A document is either one record or a list of records."""
    return doc if isinstance(doc, list) else [doc]


def check_examples() -> list[str]:
    """Validate every mapped example against its schema."""
    errors: list[str] = []
    for pattern, schema_name in EXAMPLE_MAP.items():
        validator = jsonschema.Draft202012Validator(_load(SCHEMA_DIR / schema_name))
        for example in sorted(EX_DIR.glob(pattern)):
            for record in _records(_load(example)):
                errs = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
                if errs:
                    loc = ".".join(str(p) for p in errs[0].path) or "<root>"
                    errors.append(f"{example.name}: {loc}: {errs[0].message}")
    return errors


def main() -> int:
    errors = check_schemas() + check_examples()
    if errors:
        print("schema validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    print("OK: schemas valid and all examples conform.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
