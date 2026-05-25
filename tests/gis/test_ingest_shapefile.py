"""Tests for shapefile ingestion (T05-02).

Builds tiny shapefiles with pyshp's ``shapefile.Writer`` into ``tmp_path`` (a
polygon and a point), parses them back, and asserts the recovered geometries.
Also exercises the zipped-shapefile path. No artifacts touch the repo — all
files go to pytest's ``tmp_path``. Pure Python; no GDAL.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
import shapefile
from ipermit_gis import GeometryError, parse_shapefile

SQUARE_RING = [[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0], [0.0, 0.0]]


def _write_polygon_shapefile(base: Path) -> Path:
    """Write a single-polygon shapefile at *base* (no extension); return base."""
    writer = shapefile.Writer(str(base), shapeType=shapefile.POLYGON)
    writer.field("name", "C")
    writer.poly([SQUARE_RING])
    writer.record("parcel-1")
    writer.close()
    return base


def _write_point_shapefile(base: Path) -> Path:
    """Write a single-point shapefile at *base* (no extension); return base."""
    writer = shapefile.Writer(str(base), shapeType=shapefile.POINT)
    writer.field("name", "C")
    writer.point(1.5, 2.5)
    writer.record("site-1")
    writer.close()
    return base


def test_parse_polygon_shapefile_from_path(tmp_path: Path) -> None:
    base = _write_polygon_shapefile(tmp_path / "poly")
    geometries = parse_shapefile(base.with_suffix(".shp"))
    assert len(geometries) == 1
    geom = geometries[0]
    assert geom["type"] == "Polygon"
    # Coordinates are JSON-native lists (not tuples) and assumed lon/lat.
    assert isinstance(geom["coordinates"], list)
    assert isinstance(geom["coordinates"][0][0], list)
    assert geom["coordinates"][0][0] == [0.0, 0.0]


def test_parse_point_shapefile_from_path(tmp_path: Path) -> None:
    base = _write_point_shapefile(tmp_path / "pt")
    geometries = parse_shapefile(base.with_suffix(".shp"))
    assert len(geometries) == 1
    assert geometries[0]["type"] == "Point"
    assert geometries[0]["coordinates"] == [1.5, 2.5]


def test_parse_shapefile_from_raw_shp_bytes(tmp_path: Path) -> None:
    base = _write_polygon_shapefile(tmp_path / "poly")
    raw = base.with_suffix(".shp").read_bytes()
    geometries = parse_shapefile(raw)
    assert len(geometries) == 1
    assert geometries[0]["type"] == "Polygon"


def test_parse_zipped_shapefile(tmp_path: Path) -> None:
    base = _write_polygon_shapefile(tmp_path / "poly")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for ext in (".shp", ".shx", ".dbf"):
            archive.write(base.with_suffix(ext), arcname=f"poly{ext}")
    geometries = parse_shapefile(buffer.getvalue())
    assert len(geometries) == 1
    assert geometries[0]["type"] == "Polygon"
    assert geometries[0]["coordinates"][0][0] == [0.0, 0.0]


def test_parse_empty_bytes_raises() -> None:
    with pytest.raises(GeometryError):
        parse_shapefile(b"")


def test_parse_zip_without_shp_raises(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "no shapefile here")
    with pytest.raises(GeometryError):
        parse_shapefile(buffer.getvalue())


def test_parse_unsupported_source_raises() -> None:
    with pytest.raises(GeometryError):
        parse_shapefile(12345)  # type: ignore[arg-type]
