"""Tests for the GeoJSON <-> shapely geometry helpers (T05-01).

Covers loading and back-serialization (round-trip), bbox, and the validate/
repair path on a self-intersecting "bowtie" polygon. Pure shapely; no DB, no
GDAL.
"""

from __future__ import annotations

import pytest
from ipermit_gis import (
    ASSUMED_CRS,
    GeometryError,
    bbox,
    from_geojson,
    load_valid,
    to_geojson,
    validate_geometry,
)
from shapely.geometry import Polygon

# A simple valid square (WGS84 lon/lat).
SQUARE = {
    "type": "Polygon",
    "coordinates": [[[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0], [0.0, 0.0]]],
}

# A self-intersecting "bowtie" polygon — invalid until repaired.
BOWTIE = {
    "type": "Polygon",
    "coordinates": [[[0.0, 0.0], [2.0, 2.0], [2.0, 0.0], [0.0, 2.0], [0.0, 0.0]]],
}


def test_assumed_crs_is_wgs84() -> None:
    assert ASSUMED_CRS == "EPSG:4326"


def test_from_geojson_builds_shapely_geometry() -> None:
    geom = from_geojson(SQUARE)
    assert geom.geom_type == "Polygon"
    assert geom.is_valid


def test_from_geojson_rejects_non_dict() -> None:
    with pytest.raises(GeometryError):
        from_geojson([1, 2, 3])  # type: ignore[arg-type]


def test_from_geojson_rejects_garbage() -> None:
    with pytest.raises(GeometryError):
        from_geojson({"type": "Nonsense", "coordinates": []})


def test_geojson_round_trip_is_lossless() -> None:
    geom = from_geojson(SQUARE)
    back = to_geojson(geom)
    assert back["type"] == "Polygon"
    # Coordinates come back as JSON-native lists, not tuples.
    assert isinstance(back["coordinates"], list)
    assert isinstance(back["coordinates"][0][0], list)
    # Re-loading the round-tripped dict yields an equal geometry.
    assert from_geojson(back).equals(geom)


def test_to_geojson_rejects_non_geometry() -> None:
    with pytest.raises(GeometryError):
        to_geojson({"type": "Polygon"})  # type: ignore[arg-type]


def test_bbox_returns_wgs84_bounds() -> None:
    geom = from_geojson(SQUARE)
    assert bbox(geom) == (0.0, 0.0, 2.0, 2.0)


def test_bbox_of_empty_raises() -> None:
    with pytest.raises(GeometryError):
        bbox(Polygon())


def test_validate_passes_valid_geometry_through() -> None:
    geom = from_geojson(SQUARE)
    assert validate_geometry(geom) is geom


def test_validate_repairs_self_intersecting_bowtie() -> None:
    invalid = from_geojson(BOWTIE)
    assert not invalid.is_valid
    repaired = validate_geometry(invalid)
    assert repaired.is_valid
    assert not repaired.is_empty
    # The bowtie repairs into two triangles -> a MultiPolygon.
    assert repaired.geom_type in {"Polygon", "MultiPolygon"}


def test_validate_rejects_empty_geometry() -> None:
    with pytest.raises(GeometryError):
        validate_geometry(Polygon())


def test_load_valid_parses_and_validates() -> None:
    geom = load_valid(BOWTIE)
    assert geom.is_valid
    assert not geom.is_empty
