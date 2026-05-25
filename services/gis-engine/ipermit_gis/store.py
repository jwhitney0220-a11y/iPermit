"""In-memory spatial store for jurisdiction/overlay geometries (T05-01).

:class:`GeometryStore` maps an opaque id (a ``jurisdiction_id`` per
``docs/specs/jurisdiction-naming.md`` §9, or a future overlay id) to a shapely
geometry and answers the one spatial question detection needs: *which stored
geometries intersect a target footprint?* This is the foundation that
county/municipality/ETJ detection (T05-03) and environmental-overlay detection
(T05-04) query.

In-memory-for-tests vs PostGIS-for-prod:
    This store keeps everything in a plain ``dict`` and does intersection math
    with shapely in process — no DB, no GDAL — so the whole detection path is
    deterministic and unit-testable in CI (mirroring ADR-0005's
    SQLite-for-tests / Postgres-for-prod pattern; see the package README and
    ``docs/operations/postgis-planning.md`` / T01-16).

    In **production**, this class is swapped for a PostGIS-backed store: the
    same ``(id -> geometry)`` records live in a ``geometry``/``geography``
    column with a **GiST spatial index**, and ``intersecting`` becomes a single
    ``ST_Intersects`` query that the index accelerates. The public surface
    (``add`` / ``get`` / ``intersecting``) is kept deliberately small so that
    swap is a drop-in: callers depend on this interface, not on the storage.
    The GeoAlchemy2 production path is documented in the package README; it is
    intentionally NOT wired here so tests stay DB-free.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from shapely.geometry.base import BaseGeometry

from .geometry import GeometryError, validate_geometry


class GeometryStore:
    """A deterministic, in-memory ``id -> shapely geometry`` spatial index.

    Geometries are validated (and repaired if needed) on insertion via
    :func:`~ipermit_gis.geometry.validate_geometry`, so the store never holds an
    empty or invalid shape. All ordered outputs are sorted by id for
    determinism.
    """

    def __init__(self) -> None:
        self._geoms: dict[str, BaseGeometry] = {}

    def __len__(self) -> int:
        return len(self._geoms)

    def __contains__(self, geom_id: object) -> bool:
        return geom_id in self._geoms

    def __iter__(self) -> Iterator[str]:
        """Iterate ids in deterministic (sorted) order."""
        return iter(sorted(self._geoms))

    def add(self, geom_id: str, geom: BaseGeometry, *, replace: bool = False) -> None:
        """Add a validated geometry under *geom_id*.

        Args:
            geom_id: opaque id (jurisdiction_id or overlay_id).
            geom: a shapely geometry; validated/repaired before storage.
            replace: if False (default), re-adding an existing id raises.

        Raises:
            GeometryError: if the geometry is empty/unrepairable, or if
                *geom_id* already exists and *replace* is False.
        """
        if not geom_id:
            raise GeometryError("geom_id must be a non-empty string")
        if not replace and geom_id in self._geoms:
            raise GeometryError(f"id already present in store: {geom_id!r}")
        self._geoms[geom_id] = validate_geometry(geom)

    def get(self, geom_id: str) -> BaseGeometry | None:
        """Return the geometry stored under *geom_id*, or ``None`` if absent."""
        return self._geoms.get(geom_id)

    def ids(self) -> list[str]:
        """Return all stored ids in deterministic (sorted) order."""
        return sorted(self._geoms)

    def intersecting(self, target: BaseGeometry) -> list[str]:
        """Return ids whose stored geometry intersects *target*, sorted.

        Uses shapely ``.intersects`` (boundary-touch counts as intersecting,
        matching PostGIS ``ST_Intersects``). The result is sorted by id so the
        output is deterministic across runs — detection (T05-03/T05-04) and its
        review/confirm workflow (T05-06) rely on stable ordering.

        Non-overlapping targets yield an empty list.

        Raises:
            GeometryError: if *target* is empty or not a shapely geometry.
        """
        if not isinstance(target, BaseGeometry):
            raise GeometryError(
                f"target must be a shapely geometry, got {type(target).__name__}"
            )
        if target.is_empty:
            raise GeometryError("cannot intersect an empty target geometry")
        matches = [
            geom_id for geom_id, geom in self._geoms.items() if geom.intersects(target)
        ]
        return sorted(matches)

    def extend(self, items: Iterable[tuple[str, BaseGeometry]]) -> None:
        """Add many ``(id, geometry)`` pairs (convenience over :meth:`add`)."""
        for geom_id, geom in items:
            self.add(geom_id, geom)
