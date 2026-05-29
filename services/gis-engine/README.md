# services/gis-engine

Lightweight spatial intelligence for iPermit (EPIC-05). Shapefile/KMZ ingestion
plus jurisdiction/overlay detection, built to the AGENTS.md *GIS Strategy*
("lightweight overlays only") and *GIS Intake Strategy* (upload -> auto-detect
-> user review -> confirm; manual entry as fallback).

Package: `ipermit_gis`. Delivered across T05-01 (spatial foundation) and T05-02
(shapefile/KMZ ingestion); later tickets (T05-03–T05-06) build on this seam.

## What is implemented (T05-01 / T05-02)

- `geometry.py` — GeoJSON-like `dict` <-> shapely helpers, validation with
  repair (`make_valid` / `buffer(0)` fallback), bbox, and an explicit
  WGS84 (EPSG:4326) CRS contract.
- `store.py` — `GeometryStore`: an in-memory `id -> shapely geometry` index with
  `add` / `get` / deterministic `intersecting(target)`. This is the spatial
  query surface that detection queries.
- `ingest.py` — `parse_shapefile` (pyshp; raw or zipped `.shp`/`.shx`/`.dbf`),
  `parse_kmz` / `parse_kml` (stdlib `zipfile` + `xml.etree`), and
  `normalize_footprint(...) -> ProjectFootprint` that unions parsed geometries
  into one validated footprint with a `bbox` and a `point`/`line`/`polygon`/
  `mixed` `geometry_type` summary.

## In-memory-for-tests vs PostGIS-for-prod (the core split)

The detection logic is intentionally **shapely-based and DB-free** so it runs in
CI with no system GDAL and no live PostGIS — mirroring the
SQLite-for-tests / Postgres-for-prod pattern in **ADR-0005** and the persistence
package's `engine.py`. Geometries travel as GeoJSON-like `dict`s and are loaded
into shapely shapes (bundled GEOS) for the intersection math.

In **production**, the spatial store is PostGIS, per **T01-16**
([`docs/operations/postgis-planning.md`](../../docs/operations/postgis-planning.md))
and **ADR-0001** (PostgreSQL 16 + PostGIS, managed in staging/prod;
`postgis/postgis:16-3.4` for CI/dev):

- `GeometryStore` is swapped for a PostGIS-backed store. The same
  `(id -> geometry)` records live in a **GeoAlchemy2** `Geometry`/`Geography`
  column on the iPermit shared `Base` (`packages/persistence`), with a
  **GiST spatial index**.
- `GeometryStore.intersecting(target)` becomes a single `ST_Intersects` query
  that the GiST index accelerates, instead of an in-process shapely scan.
- The public surface (`add` / `get` / `intersecting`) is kept deliberately small
  so this swap is a drop-in: callers (detection, T05-03/T05-04) depend on the
  interface, not on the storage backend.

The GeoAlchemy2 path is **wired in `ipermit_gis.postgis`** (S06-01) on a
separate `MetaData`, so the shared `Base.metadata.create_all` used by SQLite
tests does not see the `Geometry` column. The production model and store:

```python
from ipermit_gis import JurisdictionGeometry, PostGISGeometryStore

store = PostGISGeometryStore(session)        # SQLAlchemy Session
store.add("juris-abc", shapely_polygon)       # ST_GeomFromText(wkt, 4326)
store.intersecting(footprint)                 # ST_Intersects against GiST
```

Table + GiST index creation is owned by the Postgres-only Alembic migration
`migrations/versions/e5b9a2c61a47_jurisdiction_geometry_postgis.py`, which
is a no-op on SQLite.

## CRS handling (explicit, no silent reprojection)

All inputs and outputs are assumed **WGS84 (EPSG:4326)** lon/lat
(`ipermit_gis.geometry.ASSUMED_CRS`). The engine does **no** CRS detection and
**no** reprojection: it never reads a shapefile `.prj`, and it assumes lon/lat
ordering throughout. Reprojection of non-4326 sources (e.g. a Texas State Plane
shapefile) is **deferred** — callers must reproject upstream or flag the source
for manual handling. This is a deliberate "feed me 4326 or reproject first"
contract so the engine never silently mis-handles a projected source.

## Relationship to the jurisdiction model

Per [`docs/specs/jurisdiction-naming.md`](../../docs/specs/jurisdiction-naming.md)
§9, a jurisdiction record's `geometry_ref` is an **opaque pointer** to a geometry
record in this store — it holds no inline coordinates. T05-01 owns the actual
geometry storage and schema; jurisdiction records and their geometry are ingested
independently (a record may exist before its geometry).

## Dependencies (pure-pip, no apt)

- `shapely` (>=2.0) — geometry + intersection (bundles GEOS).
- `pyshp` (`shapefile`, >=2.3) — shapefile reading (pure Python).
- stdlib `zipfile` + `xml.etree` — KMZ/KML.

No `geopandas` / `fiona` / `gdal` (those need system GDAL). `shapely`/`pyshp`
are in `requirements-dev.txt`; the PostGIS path adds `geoalchemy2` (S06-01),
which ships in `services/api/requirements.txt` so it is installed in CI and
production — the live PostGIS database is only required at runtime, never at
test time.

## Deferred (clean seams, not implemented here)

- County / municipality / ETJ detection — **T05-03**
- Environmental overlays (FEMA / watershed / USACE) — **T05-04**
- GIS-driven intake modifiers — **T05-05**
- Auto-detect review / confirm workflow — **T05-06**

These build on `GeometryStore.intersecting` and the ingest parsers.
