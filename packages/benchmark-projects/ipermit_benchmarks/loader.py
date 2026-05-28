"""Load and validate benchmark project definitions (T04-02).

Benchmark projects are the regression corpus for the deterministic rules engine
(T00-06). Each file is a single benchmark object conforming to
``docs/specs/schemas/benchmark-project.schema.json`` and lives under
``packages/benchmark-projects/benchmarks/``. This module loads, parses, and
schema-validates them; running them against the engine is :mod:`.runner`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

_SCHEMA_RELPATH = "docs/specs/schemas/benchmark-project.schema.json"
_BENCH_RELPATH = "packages/benchmark-projects/benchmarks"


class BenchmarkValidationError(Exception):
    """Raised when a benchmark file fails schema validation or parsing."""


@dataclass(frozen=True)
class Benchmark:
    """A loaded benchmark project plus where it came from."""

    benchmark_id: str
    category: str
    path: Path
    data: dict[str, Any]


def repo_root(start: Path | None = None) -> Path:
    """Walk upward from *start* until the benchmark schema is found."""
    here = (start or Path(__file__)).resolve()
    for parent in (here, *here.parents):
        if (parent / _SCHEMA_RELPATH).is_file():
            return parent
    raise BenchmarkValidationError("could not locate repo root (benchmark schema)")


def load_schema(root: Path | None = None) -> dict[str, Any]:
    """Load the canonical benchmark-project JSON Schema."""
    root = root or repo_root()
    return json.loads((root / _SCHEMA_RELPATH).read_text(encoding="utf-8"))


def _parse_file(path: Path) -> dict[str, Any]:
    """Parse a single .yaml/.yml/.json benchmark file into a dict."""
    text = path.read_text(encoding="utf-8")
    data = (
        yaml.safe_load(text) if path.suffix in (".yaml", ".yml") else json.loads(text)
    )
    if not isinstance(data, dict):
        raise BenchmarkValidationError(
            f"{path}: benchmark file must be a single object"
        )
    return data


def _validate(data: dict[str, Any], path: Path, validator) -> Benchmark:
    """Validate one benchmark's schema conformance."""
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        loc = ".".join(str(p) for p in errors[0].path) or "<root>"
        raise BenchmarkValidationError(f"{path}: {loc}: {errors[0].message}")
    return Benchmark(data["benchmark_id"], data["category"], path, data)


def load_benchmarks(
    root: Path | None = None, directory: Path | None = None
) -> list[Benchmark]:
    """Load and validate every benchmark under the benchmark directory."""
    root = root or repo_root()
    base = directory or (root / _BENCH_RELPATH)
    validator = jsonschema.Draft202012Validator(load_schema(root))
    benchmarks: list[Benchmark] = []
    for pattern in ("*.yaml", "*.yml", "*.json"):
        for path in sorted(base.glob(pattern)):
            benchmarks.append(_validate(_parse_file(path), path, validator))
    return sorted(benchmarks, key=lambda b: b.benchmark_id)
