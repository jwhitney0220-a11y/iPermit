"""Tests for the in-memory GeometryStore spatial index (T05-01).

Verifies deterministic ``intersecting`` results, boundary-touch semantics,
empty results for non-overlapping targets, validation on insert, and the small
dict-like surface. Pure shapely; no DB.
"""

from __future__ import annotations

import pytest
from ipermit_gis import GeometryError, GeometryStore, from_geojson
from shapely.geometry import Polygon


def _square(x0: float, y0: float, size: float = 1.0) -> object:
    """Build a unit-ish square polygon at the given lower-left corner."""
    return from_geojson(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [x0, y0],
                    [x0, y0 + size],
                    [x0 + size, y0 + size],
                    [x0 + size, y0],
                    [x0, y0],
                ]
            ],
        }
    )


def _store_with_three() -> GeometryStore:
    store = GeometryStore()
    store.add("tx-county-a", _square(0, 0))
    store.add("tx-county-b", _square(2, 2))
    store.add("tx-county-c", _square(0.5, 0.5))
    return store


def test_add_and_get_round_trip() -> None:
    store = GeometryStore()
    geom = _square(0, 0)
    store.add("jur-1", geom)
    assert store.get("jur-1") is not None
    assert store.get("missing") is None
    assert "jur-1" in store
    assert len(store) == 1


def test_add_rejects_empty_id() -> None:
    store = GeometryStore()
    with pytest.raises(GeometryError):
        store.add("", _square(0, 0))


def test_add_duplicate_id_raises_unless_replace() -> None:
    store = GeometryStore()
    store.add("jur-1", _square(0, 0))
    with pytest.raises(GeometryError):
        store.add("jur-1", _square(1, 1))
    store.add("jur-1", _square(1, 1), replace=True)
    assert len(store) == 1


def test_intersecting_returns_overlapping_ids_sorted() -> None:
    store = _store_with_three()
    # A target overlapping the two squares anchored near the origin.
    target = _square(0.25, 0.25, size=0.5)
    result = store.intersecting(target)
    assert result == ["tx-county-a", "tx-county-c"]
    # Deterministic: repeated calls give the same order.
    assert store.intersecting(target) == result


def test_intersecting_non_overlapping_is_empty() -> None:
    store = _store_with_three()
    far_away = _square(100, 100)
    assert store.intersecting(far_away) == []


def test_intersecting_counts_boundary_touch() -> None:
    store = GeometryStore()
    store.add("a", _square(0, 0))
    # Shares only the edge x == 1 -> ST_Intersects-style touch counts.
    toucher = _square(1, 0)
    assert store.intersecting(toucher) == ["a"]


def test_intersecting_empty_target_raises() -> None:
    store = _store_with_three()
    with pytest.raises(GeometryError):
        store.intersecting(Polygon())


def test_intersecting_non_geometry_raises() -> None:
    store = _store_with_three()
    with pytest.raises(GeometryError):
        store.intersecting({"type": "Polygon"})  # type: ignore[arg-type]


def test_ids_and_iter_are_sorted() -> None:
    store = GeometryStore()
    store.add("z", _square(0, 0))
    store.add("a", _square(2, 2))
    store.add("m", _square(4, 4))
    assert store.ids() == ["a", "m", "z"]
    assert list(store) == ["a", "m", "z"]


def test_extend_adds_many() -> None:
    store = GeometryStore()
    store.extend([("a", _square(0, 0)), ("b", _square(2, 2))])
    assert store.ids() == ["a", "b"]
