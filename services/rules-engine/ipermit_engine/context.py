"""Project evaluation context for the deterministic rules engine (T03-01).

A ``ProjectContext`` is the flat namespace of evaluation inputs the engine
reads when checking a rule's triggers. Field paths are dotted, snake_case
identifiers rooted at one of three namespaces (rule-object spec §5.5):

- ``project.*``  — values from the consultant intake form (T06-02).
- ``geometry.*`` — values from GIS auto-detection (T05-03 / T05-04).
- ``derived.*``  — values computed by the engine from other inputs.

This module deliberately does **not** own the field registry — which
``project.*`` / ``geometry.*`` paths are valid is defined by T02-02 / T06-02 /
T05-04. ``ProjectContext`` accepts arbitrary documented paths and reports a
sentinel (``MISSING``) for any path the caller did not supply, so the engine
can distinguish "field absent" from "field present and null" — a distinction
the ``exists`` operator depends on.

The context is DB-free and pure: it is a typed view over a plain mapping.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

_NAMESPACES: Final = ("project", "geometry", "derived")


class _Missing:
    """Sentinel for an absent context path.

    A dedicated singleton type (rather than ``None``) lets the engine tell
    "the field was not supplied" apart from "the field was supplied as null".
    The ``exists`` operator is the only operator that treats these differently:
    a supplied ``None`` is *not* present, and an absent path is also not
    present, but every other operator collapses both to a non-match.
    """

    _instance: _Missing | None = None

    def __new__(cls) -> _Missing:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


#: Singleton returned by :meth:`ProjectContext.get` when a path is absent.
MISSING: Final[_Missing] = _Missing()


class ProjectContext:
    """A flat, dotted-path namespace of evaluation inputs.

    Construct from a mapping whose keys are full dotted paths
    (``{"project.acreage": 12.5}``) or from nested per-namespace mappings via
    :meth:`from_namespaces`. Lookups return the stored value, or :data:`MISSING`
    when the path was never supplied.
    """

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Any] | None = None) -> None:
        """Store a shallow copy of *values* keyed by full dotted path.

        Args:
            values: Mapping from dotted path (e.g. ``"project.acreage"``) to the
                input value. ``None`` is a valid value (present-but-null);
                omission of a key is what makes a path :data:`MISSING`.
        """
        self._values: dict[str, Any] = dict(values or {})

    @classmethod
    def from_namespaces(cls, **namespaces: Mapping[str, Any]) -> ProjectContext:
        """Build a context from nested per-namespace mappings.

        Example:
            ``ProjectContext.from_namespaces(project={"acreage": 12.5})``
            is equivalent to ``ProjectContext({"project.acreage": 12.5})``.

        Args:
            **namespaces: One mapping per namespace name (``project``,
                ``geometry``, ``derived``). Unknown namespace names raise.

        Raises:
            ValueError: if a namespace name is not one of the three valid roots.
        """
        flat: dict[str, Any] = {}
        for root, fields in namespaces.items():
            if root not in _NAMESPACES:
                raise ValueError(
                    f"unknown namespace {root!r}; expected one of {_NAMESPACES}"
                )
            for name, value in fields.items():
                flat[f"{root}.{name}"] = value
        return cls(flat)

    def get(self, path: str) -> Any:
        """Return the value at *path*, or :data:`MISSING` if it was not supplied.

        A path mapped to ``None`` returns ``None`` (present-but-null), which is
        distinct from :data:`MISSING`. The engine relies on this distinction for
        the ``exists`` operator.
        """
        return self._values.get(path, MISSING)

    def has(self, path: str) -> bool:
        """Return True if *path* was supplied at all (even as ``None``)."""
        return path in self._values

    def as_dict(self) -> dict[str, Any]:
        """Return a shallow copy of the underlying flat mapping."""
        return dict(self._values)

    def __repr__(self) -> str:
        return f"ProjectContext({self._values!r})"
