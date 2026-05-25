"""GeoJSON <-> shapely geometry helpers and validation (T05-01).

The spatial foundation is intentionally **DB-free and shapely-based** so it is
fully unit-testable in CI without GDAL or a live PostGIS (mirroring the
SQLite-for-tests / PostGIS-for-prod split in ADR-0005; see the package README).
Geometries travel through the engine as GeoJSON-like geometry ``dict``s and are
loaded into :mod:`shapely` shapes for the intersection math that detection
(T05-03/T05-04) builds on.

CRS assumption (explicit):
    All inputs are assumed to be **WGS84 (EPSG:4326)** lon/lat — the de-facto
    CRS of GeoJSON and the common case for uploaded KMZ. Reprojection of
    non-4326 sources (e.g. a shapefile in a State Plane projection carried in a
    ``.prj``) is **deferred**: callers must reproject upstream, or flag the
    source for manual handling. This module never silently mis-handles a
    non-4326 source — it does no CRS detection and assumes lon/lat ordering, so
    the contract is "feed me 4326 or reproject first".

Geometry repair:
    ``validate_geometry`` rejects empty geometries and attempts to repair an
    invalid one (e.g. a self-intersecting "bowtie" polygon) via shapely
    ``make_valid`` with a ``buffer(0)`` fallback. The repaired geometry is
    returned; an unrepairable or empty geometry raises :class:`GeometryError`.
"""

from __future__ import annotations

from typing import Any

from shapely.errors import ShapelyError
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

try:  # shapely >= 2.0 exposes make_valid at the top level.
    from shapely import make_valid as _make_valid
except ImportError:  # pragma: no cover - defensive for older shapely.
    _make_valid = None

#: The single CRS this engine assumes for all inputs and outputs.
ASSUMED_CRS = "EPSG:4326"

#: A WGS84 bounding box: (min_lon, min_lat, max_lon, max_lat).
BBox = tuple[float, float, float, float]


class GeometryError(ValueError):
    """Raised for empty, malformed, or unrepairable geometry input."""


def from_geojson(geojson: dict[str, Any]) -> BaseGeometry:
    """Load a GeoJSON-like geometry ``dict`` into a shapely geometry.

    Accepts the standard GeoJSON geometry shape
    (``{"type": "...", "coordinates": [...]}``) or a ``GeometryCollection``.
    Coordinates are assumed WGS84 lon/lat (:data:`ASSUMED_CRS`).

    Raises:
        GeometryError: if *geojson* is not a mapping or shapely cannot build a
            geometry from it.
    """
    if not isinstance(geojson, dict):
        raise GeometryError(
            f"expected a GeoJSON geometry dict, got {type(geojson).__name__}"
        )
    try:
        return shape(geojson)
    except (KeyError, ValueError, TypeError, AttributeError, ShapelyError) as exc:
        raise GeometryError(f"not a valid GeoJSON geometry: {exc}") from exc


def to_geojson(geom: BaseGeometry) -> dict[str, Any]:
    """Serialize a shapely geometry back to a GeoJSON-like geometry ``dict``.

    The inverse of :func:`from_geojson`; output coordinates remain WGS84
    lon/lat (:data:`ASSUMED_CRS`). Returns a plain ``dict`` so callers can JSON
    round-trip without shapely on the other side.
    """
    if not isinstance(geom, BaseGeometry):
        raise GeometryError(f"expected a shapely geometry, got {type(geom).__name__}")
    return _to_plain(mapping(geom))


def _to_plain(obj: Any) -> Any:
    """Coerce shapely's mapping output (tuples) into JSON-native lists/dicts."""
    if isinstance(obj, dict):
        return {key: _to_plain(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(item) for item in obj]
    return obj


def validate_geometry(geom: BaseGeometry) -> BaseGeometry:
    """Validate a shapely geometry, repairing it in place where possible.

    Checks, in order:
      1. non-empty — an empty geometry is meaningless as a footprint;
      2. valid via shapely ``.is_valid`` — if invalid, attempt repair with
         ``make_valid`` and then a ``buffer(0)`` fallback;
      3. the repaired result is itself non-empty and valid.

    Returns the (possibly repaired) geometry.

    Raises:
        GeometryError: if the geometry is empty or cannot be made valid.
    """
    if geom is None or geom.is_empty:
        raise GeometryError("geometry is empty")
    if geom.is_valid:
        return geom

    repaired = _repair(geom)
    if repaired is None or repaired.is_empty or not repaired.is_valid:
        raise GeometryError("geometry is invalid and could not be repaired")
    return repaired


def _repair(geom: BaseGeometry) -> BaseGeometry | None:
    """Attempt to repair an invalid geometry; return ``None`` if it cannot be."""
    if _make_valid is not None:
        try:
            candidate = _make_valid(geom)
            if candidate is not None and not candidate.is_empty and candidate.is_valid:
                return candidate
        except Exception:  # Broad: fall through to the buffer(0) repair.
            pass
    try:
        candidate = geom.buffer(0)
    except Exception:  # Broad: geometry is unrepairable.
        return None
    return candidate


def bbox(geom: BaseGeometry) -> BBox:
    """Return the WGS84 bounding box ``(min_lon, min_lat, max_lon, max_lat)``."""
    if geom is None or geom.is_empty:
        raise GeometryError("cannot compute bbox of an empty geometry")
    minx, miny, maxx, maxy = geom.bounds
    return (minx, miny, maxx, maxy)


def load_valid(geojson: dict[str, Any]) -> BaseGeometry:
    """Convenience: :func:`from_geojson` then :func:`validate_geometry`.

    The common entry point for ingest: parse a GeoJSON-like dict and return a
    validated (repaired-if-needed) shapely geometry in one call.
    """
    return validate_geometry(from_geojson(geojson))
