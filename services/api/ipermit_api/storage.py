"""Object storage seam for uploaded files (S04-03, SAAS-04).

A swappable interface (like the auth verifier and payment provider): the default
``LocalObjectStorage`` writes to a filesystem path for dev/CI; an S3-backed
provider slots in behind ``get_storage`` for staging/production without touching
call sites. Returns an opaque ``ref`` the rest of the system stores by value.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .settings import get_settings


class ObjectStorage(Protocol):
    """Minimal blob store: write bytes under a key, return an opaque ref."""

    def put(self, key: str, data: bytes, content_type: str) -> str:
        """Persist *data* under *key* and return an opaque storage reference."""
        ...


class LocalObjectStorage:
    """Filesystem-backed store under a root directory (dev/CI)."""

    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"local://{key}"


def get_storage() -> ObjectStorage:
    """FastAPI dependency: the configured object store (local by default)."""
    return LocalObjectStorage(get_settings().storage_local_path)
