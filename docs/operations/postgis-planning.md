# PostGIS & Spatial Infrastructure Planning

- **Ticket:** T01-16
- **Status:** Proposed (planning/decision ticket — implementation is T05-01)
- **Related:** [ADR-0001](../architecture/adr-0001-tech-stack.md), T01-01, T01-09 (IaC), T05-01 (spatial DB stand-up), EPIC-05

> This is a **planning** deliverable. It does not provision anything. Its job is
> to make the spatial-database requirements explicit *now* so the hosting, CI/CD,
> and staging decisions in T01-01 / T01-09 account for them before EPIC-05 begins.

## 1. Why plan this early

AGENTS.md commits to PostGIS-or-equivalent for the lightweight GIS overlays
(state/county/municipality/ETJ/watershed/FEMA/USACE detection from uploaded
shapefiles/KMZ). ADR-0001 selected **PostgreSQL 16 + PostGIS** as the single
database engine for both relational and spatial data. A spatial extension changes
hosting, backup, CI, and local-dev requirements enough that discovering it late
(at T05-01) would force rework of the IaC (T01-09) and CI (T01-07). This ticket
front-loads those constraints.

## 2. Hosting requirements for the spatial DB

| Requirement | Detail |
|-------------|--------|
| Engine | PostgreSQL 16 with the `postgis` extension (and likely `postgis_raster`, `postgis_topology` deferred until needed). |
| Extension availability | The chosen host must allow `CREATE EXTENSION postgis;` — not all managed Postgres tiers do by default. This is the single hardest hosting constraint. |
| Versioning | PostGIS 3.4+ to match PG16. Pin the version across environments (parity per the environments standard). |
| Storage | Geometry/geography columns plus spatial (GiST) indexes. Modest at MVP (Texas jurisdiction boundaries + per-project uploaded footprints), but uploads can be large; size object storage and DB separately. |
| Backups | Standard PG backups capture spatial data; no special handling, but restore tests must confirm the extension is present on restore. |
| Connection model | Pooled connections; geospatial queries can be CPU-heavy (see ADR-0001 negative consequence about offloading work off the event loop). |

## 3. CI/CD must support spatial-extension testing

- The test database in CI (T01-07) must be **PostGIS-enabled**, not plain Postgres.
  Recommended: run the official `postgis/postgis:16-3.4` Docker image as a CI
  service container so `CREATE EXTENSION postgis;` succeeds and spatial queries
  are exercised for real.
- The same image should back the local `.devcontainer` (T01-12) so local and CI
  behavior match.
- Benchmark regression (T04-02) that exercises `geometry.*` triggers needs the
  spatial DB available; account for it in the CI matrix.

## 4. Staging environment compatibility

- Staging must run the **same** PostGIS major/minor as production (environment
  parity, per [`environments.md`](./environments.md)).
- If a managed host is chosen, confirm staging and production tiers both expose
  the PostGIS extension *before* committing — some providers gate extensions by
  tier.

## 5. Managed vs self-hosted — trade-offs

| Option | Pros | Cons |
|--------|------|------|
| **Managed PostGIS** (e.g. AWS RDS/Aurora PostgreSQL, Google Cloud SQL for PostgreSQL, Azure Database for PostgreSQL — all support the PostGIS extension) | No DB ops; automated backups, HA, patching; fastest path to MVP; aligns with Maintainability priority. | Extension/version availability varies by provider and tier; less control over PostGIS point releases; cost at scale. |
| **Self-hosted** (PostGIS container on managed compute, or VM) | Full control of extensions and versions; cheapest at small scale; trivial to match `postgis/postgis` image used in CI/dev. | Team owns backups, HA, patching, security — operational burden that competes with the Maintainability priority and the small-team reality. |

## 6. Recommendation (for sign-off)

1. **Use managed PostgreSQL + PostGIS** for staging and production. The
   Maintainability priority and small-team context outweigh the control benefits
   of self-hosting. Defer the specific cloud provider to the T01-09 hosting
   decision, but **make PostGIS-extension availability a hard selection criterion**
   when choosing the provider/tier.
2. **Use the `postgis/postgis:16-3.4` Docker image** for local dev (`.devcontainer`,
   T01-12) and CI service containers (T01-07), so all non-production environments
   are byte-for-byte spatial-capable and match production's PostGIS version.
3. **Record the final provider choice** as an addendum here (or a new ADR) once
   T01-09 selects the cloud, before T05-01 stands up the database.

## 7. Open questions (resolved later, do not block)

- Specific cloud provider and managed tier → T01-09 hosting decision.
- Whether `postgis_raster` / `postgis_topology` are needed → revisit at T05-04
  (environmental overlays) if raster sources appear.
- Connection pooling technology (e.g. PgBouncer) → T01-09 / performance work.
