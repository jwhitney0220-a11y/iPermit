"""PostGIS geometry store wiring (S06-01).

The store is the production swap-in for :class:`GeometryStore`; CI has no live
PostGIS, so this suite asserts the *shape* of the model and the SQL the store
emits, without touching a database. The append-only path is exercised against
``GeometryStore`` for the in-memory equivalent — both share the contract.
"""

from __future__ import annotations

import pytest
from geoalchemy2 import Geometry
from ipermit_gis import (
    GeometryError,
    GeometryStore,
    JurisdictionGeometry,
    PostGISGeometryStore,
    from_geojson,
)
from ipermit_persistence import Base
from shapely.geometry import Polygon
from sqlalchemy.dialects import postgresql

# A square jurisdiction polygon and a project footprint that overlaps it.
JURIS = from_geojson(
    {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]],
    }
)
OVERLAPS = Polygon([(0.5, 0.5), (0.5, 1.5), (1.5, 1.5), (1.5, 0.5)])
DISJOINT = Polygon([(2.0, 2.0), (2.0, 3.0), (3.0, 3.0), (3.0, 2.0)])


def test_model_uses_separate_metadata_so_sqlite_tests_are_untouched():
    # The whole point of the separate _PostGISBase: this table must NOT live on
    # the shared Base.metadata that SQLite tests call create_all() against.
    assert "jurisdiction_geometry" not in Base.metadata.tables


def test_model_has_4326_geometry_column_and_string_pk():
    columns = {c.name: c for c in JurisdictionGeometry.__table__.columns}
    assert set(columns) == {"id", "geom"}
    assert columns["id"].primary_key is True
    assert isinstance(columns["geom"].type, Geometry)
    assert columns["geom"].type.srid == 4326


def test_intersecting_emits_st_intersects_against_postgres_dialect():
    # Compile the store's query against the PG dialect (no live DB) so the
    # ST_Intersects + ST_GeomFromText wiring is asserted by the SQL it would
    # actually send.
    store = PostGISGeometryStore(session=_NullSession())
    target = OVERLAPS
    target_wkt = target.wkt
    stmt = store._intersect_statement(target)  # type: ignore[attr-defined]
    compiled = str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "ST_Intersects" in compiled
    assert "ST_GeomFromText" in compiled
    assert target_wkt in compiled
    assert "jurisdiction_geometry" in compiled
    assert "ORDER BY" in compiled


def test_intersect_statement_rejects_non_geometry_and_empty_targets():
    store = PostGISGeometryStore(session=_NullSession())
    with pytest.raises(GeometryError):
        store._intersect_statement("not-a-geometry")  # type: ignore[arg-type]
    with pytest.raises(GeometryError):
        store._intersect_statement(Polygon())


def test_in_memory_store_remains_the_contract_for_intersection_math():
    # Sanity: the in-memory store's intersection semantics — which the PostGIS
    # store mirrors via ST_Intersects — pick up boundary overlap and reject
    # disjoint polygons. Keeps both backends honest against one expectation.
    store = GeometryStore()
    store.add("juris-a", JURIS)
    assert store.intersecting(OVERLAPS) == ["juris-a"]
    assert store.intersecting(DISJOINT) == []


class _NullSession:
    """Stand-in session for SQL-shape tests (no execute is performed)."""

    def get(self, *_a, **_kw):  # pragma: no cover - defensive
        return None
