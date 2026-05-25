"""Executable benchmark regression framework (T04-02).

Loads benchmark project definitions (T00-06 shape) and runs them through the
T04-01 simulation engine, comparing the deterministic output against each
benchmark's expectations.

Public surface:

- loader  — ``load_benchmarks`` / ``Benchmark`` / ``BenchmarkValidationError``.
- runner  — ``run_benchmarks`` / ``run_benchmark`` / ``BenchmarkResult``.
"""

from .loader import (
    Benchmark,
    BenchmarkValidationError,
    load_benchmarks,
    load_schema,
    repo_root,
)
from .runner import BenchmarkResult, run_benchmark, run_benchmarks

__all__ = [
    "Benchmark",
    "BenchmarkResult",
    "BenchmarkValidationError",
    "load_benchmarks",
    "load_schema",
    "repo_root",
    "run_benchmark",
    "run_benchmarks",
]
