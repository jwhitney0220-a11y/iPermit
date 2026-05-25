"""Shapefile & KMZ/KML ingestion into GeoJSON-like geometries (T05-02).

This is the upload entry point of the AGENTS.md *GIS Intake Strategy*: a user
uploads a shapefile or KMZ describing a project footprint (a linear route, a
parcel polygon, or a point), and the engine parses it into GeoJSON-like geometry
``dict``s and collapses them into a single validated
:class:`ProjectFootprint`. Detection (T05-03/T05-04) then queries that footprint
against the :class:`~ipermit_gis.store.GeometryStore`.

Pure-pip, no GDAL:
    Shapefiles are read with :mod:`shapefile` (pyshp — pure Python); KMZ is a
    zip parsed with stdlib :mod:`zipfile`, and the inner KML is parsed with
    stdlib :mod:`xml.etree`. Geometry math runs on :mod:`shapely` (bundled
    GEOS). Nothing here needs system GDAL/fiona/geopandas, so the whole path is
    unit-testable in CI (see the package README).

CRS assumption (explicit):
    All sources are assumed **WGS84 (EPSG:4326)** lon/lat, matching
    :data:`ipermit_gis.geometry.ASSUMED_CRS`. A shapefile may ship a ``.prj``
    declaring a different projection (e.g. a Texas State Plane CRS); this module
    does **not** read ``.prj`` and does **not** reproject — reprojection of
    non-4326 sources is deferred (callers reproject upstream or flag for manual
    handling). It never silently mis-handles a projected source: it assumes
    lon/lat ordering and leaves coordinates untouched.

Supported geometry inputs (AGENTS.md MVP):
    Point, MultiPoint, LineString (linear routes), MultiLineString, Polygon
    (parcels / ROW), and MultiPolygon. Mixed inputs are unioned into one
    footprint.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import shapefile  # pyshp
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .geometry import GeometryError, bbox, from_geojson, to_geojson, validate_geometry

#: Bytes or a filesystem path identifying an upload.
Source = bytes | str | Path

#: A KML coordinate token must carry at least lon and lat (altitude optional).
_MIN_COORD_PARTS = 2

#: The KML element namespaces we recognize (OGC 2.2 and the older Google ns).
_KML_NAMESPACES = (
    "http://www.opengis.net/kml/2.2",
    "http://earth.google.com/kml/2.0",
    "http://earth.google.com/kml/2.1",
)

#: KML geometry tags handled as standalone geometries. ``LinearRing`` is
#: deliberately absent: rings only appear inside a ``Polygon`` boundary and are
#: consumed there, never emitted as a separate LineString.
_KML_GEOM_TAGS = {
    "Point": "Point",
    "LineString": "LineString",
    "Polygon": "Polygon",
}


class ProjectFootprint:
    """A single validated project footprint assembled from parsed geometries.

    Holds the unioned shapely geometry plus convenience accessors detection and
    the review/confirm workflow (T05-06) consume: the GeoJSON-like geometry, the
    WGS84 bbox, and a coarse ``geometry_type`` summary ("point" / "line" /
    "polygon" / "mixed") aligned with the AGENTS.md linear-vs-nonlinear split.
    """

    def __init__(self, geometry: BaseGeometry) -> None:
        self.geometry: BaseGeometry = geometry

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """WGS84 ``(min_lon, min_lat, max_lon, max_lat)`` of the footprint."""
        return bbox(self.geometry)

    @property
    def geometry_type(self) -> str:
        """Coarse summary: ``point`` / ``line`` / ``polygon`` / ``mixed``."""
        return _summarize_type(self.geometry)

    def to_geojson(self) -> dict[str, Any]:
        """Return the footprint as a GeoJSON-like geometry ``dict``."""
        return to_geojson(self.geometry)

    def __repr__(self) -> str:
        return f"ProjectFootprint(type={self.geometry_type!r}, bbox={self.bbox!r})"


def parse_shapefile(data: Source) -> list[dict[str, Any]]:
    """Parse a shapefile into a list of GeoJSON-like geometry ``dict``s.

    Accepts:
      * a filesystem path (``str``/``Path``) to a ``.shp`` (its ``.shx``/``.dbf``
        siblings are read by pyshp), or
      * raw ``bytes`` of either a single ``.shp`` stream or a ``.zip`` archive
        containing the ``.shp``/``.shx``/``.dbf`` set.

    Coordinates are returned as-is, assumed WGS84 lon/lat (no reprojection).

    Raises:
        GeometryError: if the source is empty, unreadable, or has no shapes.
    """
    if isinstance(data, (str, Path)):
        shapes = _read_shapefile_path(Path(data))
    elif isinstance(data, (bytes, bytearray)):
        shapes = _read_shapefile_bytes(bytes(data))
    else:
        raise GeometryError(f"unsupported shapefile source: {type(data).__name__}")

    geometries = [s.__geo_interface__ for s in shapes if not _is_null_shape(s)]
    if not geometries:
        raise GeometryError("shapefile contained no usable shapes")
    return [_to_plain(geom) for geom in geometries]


def _read_shapefile_path(path: Path) -> list[Any]:
    """Read shapes from a ``.shp`` on disk via pyshp."""
    try:
        reader = shapefile.Reader(str(path))
        return list(reader.shapes())
    except (shapefile.ShapefileException, OSError, ValueError) as exc:
        raise GeometryError(f"could not read shapefile {path}: {exc}") from exc


def _read_shapefile_bytes(data: bytes) -> list[Any]:
    """Read shapes from raw ``.shp`` bytes or a zipped shapefile."""
    if not data:
        raise GeometryError("empty shapefile bytes")
    if zipfile.is_zipfile(io.BytesIO(data)):
        return _read_zipped_shapefile(data)
    try:
        reader = shapefile.Reader(shp=io.BytesIO(data))
        return list(reader.shapes())
    except (shapefile.ShapefileException, ValueError) as exc:
        raise GeometryError(f"could not read .shp bytes: {exc}") from exc


def _read_zipped_shapefile(data: bytes) -> list[Any]:
    """Read shapes from a ``.zip`` containing a ``.shp``/``.shx``/``.dbf`` set."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = {Path(n).suffix.lower(): n for n in archive.namelist()}
        shp_name = members.get(".shp")
        if shp_name is None:
            raise GeometryError("zip archive has no .shp member")
        streams: dict[str, io.BytesIO] = {}
        for ext in (".shp", ".shx", ".dbf"):
            name = members.get(ext)
            if name is not None:
                streams[ext.lstrip(".")] = io.BytesIO(archive.read(name))
        try:
            reader = shapefile.Reader(**streams)
            return list(reader.shapes())
        except (shapefile.ShapefileException, ValueError) as exc:
            raise GeometryError(f"could not read zipped shapefile: {exc}") from exc


def _is_null_shape(shape: Any) -> bool:
    """True for pyshp NULL shapes (shapeType 0), which have no geometry."""
    return getattr(shape, "shapeType", None) == shapefile.NULL


def parse_kmz(data: bytes) -> list[dict[str, Any]]:
    """Parse KMZ bytes (a zip containing ``doc.kml``) into geometry ``dict``s.

    Locates the first ``.kml`` member (preferring ``doc.kml`` per the OGC KMZ
    convention), decodes it, and delegates to :func:`parse_kml`.

    Raises:
        GeometryError: if *data* is not a zip, has no KML member, or the KML
            yields no geometries.
    """
    if not data or not zipfile.is_zipfile(io.BytesIO(data)):
        raise GeometryError("KMZ source is not a zip archive")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        kml_name = _select_kml_member(archive.namelist())
        if kml_name is None:
            raise GeometryError("KMZ archive contains no .kml member")
        text = archive.read(kml_name).decode("utf-8")
    return parse_kml(text)


def _select_kml_member(names: list[str]) -> str | None:
    """Pick the KML member: prefer ``doc.kml``, else the first ``.kml``."""
    kml_members = [n for n in names if n.lower().endswith(".kml")]
    if not kml_members:
        return None
    for name in kml_members:
        if Path(name).name.lower() == "doc.kml":
            return name
    return sorted(kml_members)[0]


def parse_kml(text: str) -> list[dict[str, Any]]:
    """Parse KML text into a list of GeoJSON-like geometry ``dict``s.

    Walks every ``Point``/``LineString``/``LinearRing``/``Polygon`` element
    (namespace-agnostic) and converts its ``<coordinates>`` into GeoJSON-like
    geometry. KML coordinates are ``lon,lat[,alt]``; the altitude (3rd value) is
    dropped to keep the engine 2-D and 4326 lon/lat.

    Raises:
        GeometryError: if the text is not parseable XML or yields no geometry.
    """
    if not text or not text.strip():
        raise GeometryError("empty KML text")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise GeometryError(f"could not parse KML XML: {exc}") from exc

    geometries: list[dict[str, Any]] = []
    _collect_kml_geometries(root, geometries)
    if not geometries:
        raise GeometryError("KML contained no usable geometries")
    return geometries


def _collect_kml_geometries(element: ET.Element, out: list[dict[str, Any]]) -> None:
    """Recursively gather geometries, consuming Polygons without descending.

    A ``Polygon``'s boundary rings are handled in full by
    :func:`_kml_polygon_to_geojson`, so we do **not** recurse into a Polygon —
    that prevents its boundary from being double-counted as a standalone line.
    """
    local = _local_name(element.tag)
    geom_type = _KML_GEOM_TAGS.get(local)
    if geom_type is not None:
        geom = _kml_element_to_geojson(element, geom_type)
        if geom is not None:
            out.append(geom)
        if geom_type == "Polygon":
            return
    for child in element:
        _collect_kml_geometries(child, out)


def _kml_element_to_geojson(
    element: ET.Element, geom_type: str
) -> dict[str, Any] | None:
    """Convert one KML geometry element into a GeoJSON-like geometry dict."""
    if geom_type == "Polygon":
        return _kml_polygon_to_geojson(element)
    coords_text = _find_coordinates_text(element)
    if coords_text is None:
        return None
    coords = _parse_coordinates(coords_text)
    if not coords:
        return None
    if geom_type == "Point":
        return {"type": "Point", "coordinates": coords[0]}
    return {"type": "LineString", "coordinates": coords}


def _kml_polygon_to_geojson(element: ET.Element) -> dict[str, Any] | None:
    """Convert a KML ``Polygon`` (outer + inner rings) to GeoJSON coordinates."""
    rings: list[list[list[float]]] = []
    outer = _find_child_by_local(element, "outerBoundaryIs")
    if outer is not None:
        ring = _ring_coords(outer)
        if ring:
            rings.append(ring)
    for inner in _find_children_by_local(element, "innerBoundaryIs"):
        ring = _ring_coords(inner)
        if ring:
            rings.append(ring)
    if not rings:
        return None
    return {"type": "Polygon", "coordinates": rings}


def _ring_coords(boundary: ET.Element) -> list[list[float]]:
    """Extract a closed ring's coordinates from a KML boundary element."""
    text = _find_coordinates_text(boundary)
    if text is None:
        return []
    coords = _parse_coordinates(text)
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])  # Close the ring (GeoJSON requires it).
    return coords


def _find_coordinates_text(element: ET.Element) -> str | None:
    """Return the text of the first descendant ``<coordinates>`` element."""
    for descendant in element.iter():
        if _local_name(descendant.tag) == "coordinates" and descendant.text:
            return descendant.text
    return None


def _parse_coordinates(text: str) -> list[list[float]]:
    """Parse KML ``coordinates`` text into ``[[lon, lat], ...]`` (alt dropped)."""
    points: list[list[float]] = []
    for token in text.replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) < _MIN_COORD_PARTS:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        points.append([lon, lat])
    return points


def _local_name(tag: str) -> str:
    """Strip any ``{namespace}`` prefix from an XML tag, returning the local name."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_child_by_local(element: ET.Element, local: str) -> ET.Element | None:
    """First direct child whose local tag name equals *local*, else ``None``."""
    for child in element:
        if _local_name(child.tag) == local:
            return child
    return None


def _find_children_by_local(element: ET.Element, local: str) -> list[ET.Element]:
    """All direct children whose local tag name equals *local*."""
    return [child for child in element if _local_name(child.tag) == local]


def normalize_footprint(geometries: list[dict[str, Any]]) -> ProjectFootprint:
    """Union parsed GeoJSON-like geometries into one validated footprint.

    Loads each geometry into shapely, unions them (``unary_union``), and
    validates/repairs the result so the footprint is never empty or invalid.
    Mixed inputs (e.g. a route line plus a parcel polygon) collapse into a single
    geometry whose :attr:`ProjectFootprint.geometry_type` reports ``mixed``.

    Raises:
        GeometryError: if *geometries* is empty or yields an empty/invalid union.
    """
    if not geometries:
        raise GeometryError("cannot normalize an empty list of geometries")
    shapes = [from_geojson(geom) for geom in geometries]
    shapes = [s for s in shapes if s is not None and not s.is_empty]
    if not shapes:
        raise GeometryError("all input geometries were empty")
    merged = shapes[0] if len(shapes) == 1 else unary_union(shapes)
    return ProjectFootprint(validate_geometry(merged))


def _summarize_type(geom: BaseGeometry) -> str:
    """Map a shapely geometry's type to point / line / polygon / mixed."""
    name = geom.geom_type
    point_types = {"Point", "MultiPoint"}
    line_types = {"LineString", "MultiLineString", "LinearRing"}
    polygon_types = {"Polygon", "MultiPolygon"}
    if name in point_types:
        return "point"
    if name in line_types:
        return "line"
    if name in polygon_types:
        return "polygon"
    return "mixed"


def _to_plain(obj: Any) -> Any:
    """Coerce pyshp's geo-interface output (tuples) into JSON-native lists."""
    if isinstance(obj, dict):
        return {key: _to_plain(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(item) for item in obj]
    return obj
