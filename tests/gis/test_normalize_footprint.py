"""Tests for normalize_footprint -> ProjectFootprint (T05-02).

Collects mixed parsed geometries (a line + a polygon) into a single validated
footprint, checks the bbox and geometry_type summary, and verifies empty/invalid
input raises GeometryError. Pure shapely; no DB.
"""

from __future__ import annotations

import pytest
from ipermit_gis import GeometryError, ProjectFootprint, normalize_footprint

POLYGON = {
    "type": "Polygon",
    "coordinates": [[[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0], [0.0, 0.0]]],
}
LINE = {"type": "LineString", "coordinates": [[0.0, 0.0], [5.0, 5.0]]}
POINT = {"type": "Point", "coordinates": [1.0, 1.0]}


def test_normalize_single_polygon() -> None:
    footprint = normalize_footprint([POLYGON])
    assert isinstance(footprint, ProjectFootprint)
    assert footprint.geometry_type == "polygon"
    assert footprint.bbox == (0.0, 0.0, 2.0, 2.0)


def test_normalize_single_line() -> None:
    footprint = normalize_footprint([LINE])
    assert footprint.geometry_type == "line"
    assert footprint.bbox == (0.0, 0.0, 5.0, 5.0)


def test_normalize_single_point() -> None:
    footprint = normalize_footprint([POINT])
    assert footprint.geometry_type == "point"


def test_normalize_mixed_line_and_polygon_unions() -> None:
    footprint = normalize_footprint([LINE, POLYGON])
    # A line + a polygon collapse into a single mixed geometry.
    assert footprint.geometry_type == "mixed"
    # The bbox spans both inputs (line reaches 5,5).
    assert footprint.bbox == (0.0, 0.0, 5.0, 5.0)


def test_normalize_footprint_to_geojson_round_trips() -> None:
    footprint = normalize_footprint([POLYGON])
    geojson = footprint.to_geojson()
    assert geojson["type"] == "Polygon"
    assert isinstance(geojson["coordinates"], list)


def test_normalize_empty_list_raises() -> None:
    with pytest.raises(GeometryError):
        normalize_footprint([])


def test_normalize_all_empty_geometries_raises() -> None:
    empty_poly = {"type": "Polygon", "coordinates": []}
    with pytest.raises(GeometryError):
        normalize_footprint([empty_poly])


def test_normalize_repairs_invalid_input() -> None:
    bowtie = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 2], [2, 0], [0, 2], [0, 0]]],
    }
    footprint = normalize_footprint([bowtie])
    assert footprint.geometry.is_valid


def test_footprint_repr_is_informative() -> None:
    footprint = normalize_footprint([POLYGON])
    text = repr(footprint)
    assert "ProjectFootprint" in text
    assert "polygon" in text
