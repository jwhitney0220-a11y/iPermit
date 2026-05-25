"""Tests for KML / KMZ ingestion (T05-02).

Parses a small KML document (a Polygon plus a LineString), then zips it into KMZ
bytes (``doc.kml`` inside a zip) and parses that. Asserts the recovered
coordinates. Pure stdlib (``zipfile`` + ``xml.etree``); no GDAL.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from ipermit_gis import GeometryError, parse_kml, parse_kmz

# A KML with the OGC 2.2 namespace, one Polygon and one LineString.
KML_TEXT = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Parcel</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              0,0,0 0,2,0 2,2,0 2,0,0 0,0,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Route</name>
      <LineString>
        <coordinates>-97.0,30.0 -97.5,30.5 -98.0,31.0</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""


def test_parse_kml_extracts_polygon_and_linestring() -> None:
    geometries = parse_kml(KML_TEXT)
    types = sorted(g["type"] for g in geometries)
    assert types == ["LineString", "Polygon"]


def test_parse_kml_polygon_coordinates_drop_altitude() -> None:
    geometries = parse_kml(KML_TEXT)
    polygon = next(g for g in geometries if g["type"] == "Polygon")
    ring = polygon["coordinates"][0]
    # Altitude (3rd value) dropped; ring closed; lon/lat preserved.
    assert ring[0] == [0.0, 0.0]
    assert ring[-1] == ring[0]
    assert [2.0, 2.0] in ring


def test_parse_kml_linestring_coordinates() -> None:
    geometries = parse_kml(KML_TEXT)
    line = next(g for g in geometries if g["type"] == "LineString")
    assert line["coordinates"][0] == [-97.0, 30.0]
    assert line["coordinates"][-1] == [-98.0, 31.0]


def test_parse_kml_handles_point() -> None:
    text = """<?xml version="1.0"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Placemark><Point><coordinates>-97.7,30.3,0</coordinates></Point></Placemark>
    </kml>"""
    geometries = parse_kml(text)
    assert geometries[0]["type"] == "Point"
    assert geometries[0]["coordinates"] == [-97.7, 30.3]


def test_parse_kml_empty_text_raises() -> None:
    with pytest.raises(GeometryError):
        parse_kml("   ")


def test_parse_kml_no_geometry_raises() -> None:
    text = '<kml xmlns="http://www.opengis.net/kml/2.2"><Document/></kml>'
    with pytest.raises(GeometryError):
        parse_kml(text)


def test_parse_kml_bad_xml_raises() -> None:
    with pytest.raises(GeometryError):
        parse_kml("<kml><unclosed>")


def _kmz_bytes(kml_text: str, member: str = "doc.kml") -> bytes:
    """Zip *kml_text* into KMZ bytes under *member*."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, kml_text)
    return buffer.getvalue()


def test_parse_kmz_round_trips_kml() -> None:
    geometries = parse_kmz(_kmz_bytes(KML_TEXT))
    types = sorted(g["type"] for g in geometries)
    assert types == ["LineString", "Polygon"]


def test_parse_kmz_prefers_doc_kml() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("extra.kml", "<kml/>")  # would yield no geometry
        archive.writestr("doc.kml", KML_TEXT)
    geometries = parse_kmz(buffer.getvalue())
    assert len(geometries) == 2


def test_parse_kmz_non_zip_raises() -> None:
    with pytest.raises(GeometryError):
        parse_kmz(b"not a zip")


def test_parse_kmz_without_kml_raises() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "no kml")
    with pytest.raises(GeometryError):
        parse_kmz(buffer.getvalue())
