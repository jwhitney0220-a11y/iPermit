"""iPermit lightweight GIS spatial engine (EPIC-05, T05-01/T05-02).

The DB-free spatial foundation for iPermit's GIS intake (AGENTS.md *GIS
Strategy* / *GIS Intake Strategy*): a user uploads a shapefile or KMZ, the
engine parses it into GeoJSON-like geometries, collapses them into a single
project footprint, and answers the one spatial question detection needs — which
stored jurisdiction/overlay geometries intersect that footprint?

All geometry and intersection math runs on :mod:`shapely` (bundled GEOS) over
GeoJSON-like ``dict``s, with no GDAL and no live PostGIS, so the whole path is
deterministic and unit-testable in CI. Production swaps the in-memory
:class:`GeometryStore` for a PostGIS/GeoAlchemy2-backed store with a GiST index
(mirroring ADR-0005's SQLite-for-tests / Postgres-for-prod split; see README).

Public surface:

- geometry  — GeoJSON <-> shapely helpers, validation/repair, bbox
  (``from_geojson`` / ``to_geojson`` / ``load_valid`` / ``validate_geometry`` /
  ``bbox`` / ``ASSUMED_CRS`` / ``GeometryError``) — T05-01.
- store     — ``GeometryStore``: in-memory ``id -> geometry`` spatial index with
  deterministic ``intersecting`` — T05-01.
- ingest    — shapefile/KMZ/KML parsers and ``normalize_footprint`` ->
  ``ProjectFootprint`` — T05-02.
"""

from .geometry import (
    ASSUMED_CRS,
    BBox,
    GeometryError,
    bbox,
    from_geojson,
    load_valid,
    to_geojson,
    validate_geometry,
)
from .ingest import (
    ProjectFootprint,
    normalize_footprint,
    parse_kml,
    parse_kmz,
    parse_shapefile,
)
from .store import GeometryStore

__all__ = [
    "ASSUMED_CRS",
    "BBox",
    "GeometryError",
    "GeometryStore",
    "ProjectFootprint",
    "bbox",
    "from_geojson",
    "load_valid",
    "normalize_footprint",
    "parse_kml",
    "parse_kmz",
    "parse_shapefile",
    "to_geojson",
    "validate_geometry",
]
