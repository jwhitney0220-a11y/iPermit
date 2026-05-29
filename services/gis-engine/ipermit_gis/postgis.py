"""PostGIS-backed geometry store (S06-01).

Production swap-in for :class:`~ipermit_gis.store.GeometryStore`. The package
README describes the design contract; this module is the wiring: a
GeoAlchemy2 ``Geometry`` column on a *separate* SQLAlchemy ``MetaData`` (so the
shared ``Base.metadata.create_all`` used by SQLite tests never tries to emit a
``Geometry`` column the SQLite driver can't handle), and a small
``PostGISGeometryStore`` that mirrors the in-memory store's ``add`` / ``get`` /
``intersecting`` surface against ``ST_Intersects`` over a GiST index.

CRS contract is identical to :mod:`ipermit_gis.geometry`: every geometry is
WGS84 (EPSG:4326). The store does not reproject — callers feed it 4326 or it is
their responsibility to reproject upstream.

Table / index creation is owned by a Postgres-only Alembic migration (see
``migrations/versions/<id>_jurisdiction_geometry_postgis.py``), which is a
no-op on SQLite so the test suite stays DB-free.
"""

from __future__ import annotations

from collections.abc import Iterable

from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_Intersects
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import MetaData, String, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .geometry import GeometryError, validate_geometry

#: Separate metadata so the PostGIS-only ``jurisdiction_geometry`` table never
#: lands on the shared ``ipermit_persistence.Base.metadata``. Tests do
#: ``Base.metadata.create_all`` against SQLite; that path would crash on a
#: ``Geometry`` column. Production creates this table via an Alembic migration.
_postgis_metadata = MetaData()


class _PostGISBase(DeclarativeBase):
    metadata = _postgis_metadata


class JurisdictionGeometry(_PostGISBase):
    """Production-only spatial row: an opaque id -> PostGIS geometry.

    ``id`` matches the ``geometry_ref`` on a jurisdiction record (see
    ``docs/specs/jurisdiction-naming.md`` §9). ``geom`` is a 4326 ``Geometry``
    with a GiST index created by the migration; the index is what makes
    ``ST_Intersects`` cheap at the scale of full state coverage.
    """

    __tablename__ = "jurisdiction_geometry"

    id: Mapped[str] = mapped_column(String(length=64), primary_key=True)
    geom: Mapped[object] = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326))


class PostGISGeometryStore:
    """A SQLAlchemy-backed spatial store with the same surface as
    :class:`~ipermit_gis.store.GeometryStore`.

    ``add`` / ``get`` / ``intersecting`` accept and return shapely geometries
    (the same as the in-memory store), so detection / confirmation code does
    not care which backend it talks to. The session is the caller's; this
    class never opens transactions or commits.

    The store flushes after ``add`` so a subsequent ``get`` / ``intersecting``
    in the same session sees the row; the caller still owns the commit.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, geom_id: str, geom: BaseGeometry, *, replace: bool = False) -> None:
        """Insert (or replace) a validated geometry under *geom_id*."""
        if not geom_id:
            raise GeometryError("geom_id must be a non-empty string")
        validated = validate_geometry(geom)
        existing = self._session.get(JurisdictionGeometry, geom_id)
        if existing is not None:
            if not replace:
                raise GeometryError(f"id already present in store: {geom_id!r}")
            existing.geom = from_shape(validated, srid=4326)
        else:
            self._session.add(
                JurisdictionGeometry(id=geom_id, geom=from_shape(validated, srid=4326))
            )
        self._session.flush()

    def get(self, geom_id: str) -> BaseGeometry | None:
        """Return the geometry stored under *geom_id* (or ``None``)."""
        row = self._session.get(JurisdictionGeometry, geom_id)
        return None if row is None else to_shape(row.geom)

    def _intersect_statement(self, target: BaseGeometry):
        """Build the ``ST_Intersects`` SELECT for *target*; no DB round trip."""
        if not isinstance(target, BaseGeometry):
            raise GeometryError(
                f"target must be a shapely geometry, got {type(target).__name__}"
            )
        if target.is_empty:
            raise GeometryError("cannot intersect an empty target geometry")
        target_geom = func.ST_GeomFromText(target.wkt, 4326)
        return (
            select(JurisdictionGeometry.id)
            .where(ST_Intersects(JurisdictionGeometry.geom, target_geom))
            .order_by(JurisdictionGeometry.id)
        )

    def intersecting(self, target: BaseGeometry) -> list[str]:
        """Return ids whose stored geometry intersects *target*, sorted.

        Translates directly to ``ST_Intersects(geom, ST_GeomFromText(...))``
        in one round trip; the GiST index on ``geom`` keeps this cheap.
        """
        return list(self._session.scalars(self._intersect_statement(target)))

    def extend(self, items: Iterable[tuple[str, BaseGeometry]]) -> None:
        """Add many ``(id, geometry)`` pairs (convenience over :meth:`add`)."""
        for geom_id, geom in items:
            self.add(geom_id, geom)


__all__ = ["JurisdictionGeometry", "PostGISGeometryStore"]
