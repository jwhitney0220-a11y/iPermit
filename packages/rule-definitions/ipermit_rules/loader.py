"""Load and validate declarative rule objects from the ``rules/`` tree.

The rule store is the version-controlled home for regulatory rules (T01-03).
Rules are data, not code (AGENTS.md *Rules Engine Architecture*): each file is a
single rule object conforming to ``docs/specs/schemas/rule-object.schema.json``
(T00-01) and lives in the directory matching its ``status`` field
(``rules/{draft,published,effective,archived}``, per T00-03).

This module loads, parses, and validates those files. It does not evaluate them
— evaluation is the rules engine (EPIC-03).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import jsonschema
import yaml

STATUSES = ("draft", "published", "effective", "archived")
_SCHEMA_RELPATH = "docs/specs/schemas/rule-object.schema.json"


class RuleValidationError(Exception):
    """Raised when a rule file fails schema or placement validation."""


@dataclass(frozen=True)
class Rule:
    """A loaded rule object plus where it came from."""

    rule_id: str
    version: str
    status: str
    path: Path
    data: dict[str, Any]


def repo_root(start: Path | None = None) -> Path:
    """Walk upward from ``start`` until a directory containing ``rules/`` is found."""
    here = (start or Path(__file__)).resolve()
    for parent in (here, *here.parents):
        if (parent / "rules").is_dir() and (parent / _SCHEMA_RELPATH).is_file():
            return parent
    raise RuleValidationError("could not locate repo root (rules/ + schema)")


def load_schema(root: Path | None = None) -> dict[str, Any]:
    """Load the canonical rule-object JSON Schema."""
    root = root or repo_root()
    return json.loads((root / _SCHEMA_RELPATH).read_text())


def _parse_file(path: Path) -> dict[str, Any]:
    """Parse a single .yaml/.yml/.json rule file into a dict."""
    text = path.read_text()
    data = yaml.safe_load(text) if path.suffix in (".yaml", ".yml") else json.loads(text)
    if not isinstance(data, dict):
        raise RuleValidationError(f"{path}: rule file must contain a single object")
    return data


def _rule_files(root: Path, statuses: Iterable[str]) -> list[Path]:
    """Collect all rule files under the requested status directories."""
    files: list[Path] = []
    for status in statuses:
        base = root / "rules" / status
        for pattern in ("*.yaml", "*.yml", "*.json"):
            files.extend(sorted(base.glob(pattern)))
    return files


def _validate(data: dict[str, Any], path: Path, status: str, validator) -> Rule:
    """Validate one rule's schema conformance and directory placement."""
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        loc = ".".join(str(p) for p in errors[0].path) or "<root>"
        raise RuleValidationError(f"{path}: {loc}: {errors[0].message}")
    if data.get("status") != status:
        raise RuleValidationError(
            f"{path}: status '{data.get('status')}' does not match directory '{status}'"
        )
    return Rule(data["rule_id"], data["version"], status, path, data)


def load_rules(root: Path | None = None, statuses: Iterable[str] = STATUSES) -> list[Rule]:
    """Load and validate every rule under the given status directories."""
    root = root or repo_root()
    validator = jsonschema.Draft202012Validator(load_schema(root))
    rules: list[Rule] = []
    for status in statuses:
        for path in _rule_files(root, [status]):
            rules.append(_validate(_parse_file(path), path, status, validator))
    return rules
