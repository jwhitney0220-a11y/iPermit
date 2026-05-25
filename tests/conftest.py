"""Pytest bootstrap for the monorepo (T01-07 / T02-01).

Puts the local package source roots on sys.path so tests can import
``ipermit_*`` packages without an install step. Runs before test modules are
imported, so test files can import the packages at module top level.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_PACKAGE_ROOTS = (
    "persistence",
    "jurisdiction-models",
    "rule-definitions",
    "shared-schemas/python",
)

for _rel in _PACKAGE_ROOTS:
    _path = ROOT / "packages" / _rel
    if _path.is_dir():
        sys.path.insert(0, str(_path))
