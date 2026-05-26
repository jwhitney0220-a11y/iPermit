# iPermit SaaS v1 Build Review (as of May 26, 2026)

## 1) What was actually changed by the last implementation agent
The latest implementation commit is `eba3d22` (`T05-01/T05-02: GIS spatial foundation and shapefile/KMZ ingestion`).

### Added/updated capabilities
- Shapefile/KML ingestion entrypoints and normalization paths.
- Geometry helper logic for project footprint handling.
- Storage integration helpers for GIS-engine persistence pathways.
- Dedicated GIS tests for geometry, ingest, normalization, and storage behavior.

### Files touched in that commit
- `requirements-dev.txt`
- `services/gis-engine/README.md`
- `services/gis-engine/ipermit_gis/__init__.py`
- `services/gis-engine/ipermit_gis/geometry.py`
- `services/gis-engine/ipermit_gis/ingest.py`
- `services/gis-engine/ipermit_gis/store.py`
- `tests/conftest.py`
- `tests/gis/test_geometry.py`
- `tests/gis/test_ingest_kml.py`
- `tests/gis/test_ingest_shapefile.py`
- `tests/gis/test_normalize_footprint.py`
- `tests/gis/test_store.py`

## 2) Fit against the redefined SaaS roadmap
This repo now has strong deterministic foundations (rules engine, benchmarks, regulatory models) and an initial GIS ingestion base. The core SaaS control plane remains mostly unimplemented.

### In place or near-ready
- Deterministic rule simulation and explainability primitives.
- Benchmark project regression harness.
- Regulatory temporal/freshness model layer.
- Initial GIS ingest + normalization + test coverage.

### Missing for SAAS productization
- Tenant-scoped persistence and RLS hardening.
- AuthenticatedIdentity, password/JWT auth, RBAC/roles.
- FastAPI SaaS envelope + RFC-9457 problem-details surface.
- Consultant SPA flow (login -> intake -> evaluate -> matrix).
- Audit event chain (minimal first, then hash-chain).
- Billing/metering/webhooks and entitlement gating.
- Ops portal, publication workflows, deploy/observability.

## 3) Priority execution path (enforce dependencies)
1. **SAAS-01** (S01-01 through S01-07) as the thin vertical slice.
2. **SAAS-02** depth (RBAC completion, hash-chain audit, persistence revisions, exports, feedback queue).
3. **SAAS-03** billing after authz + tenancy controls stabilize.
4. **SAAS-04/SAAS-05** consultant/admin depth after SAAS-01 APIs settle.
5. **SAAS-06/SAAS-07** spatial backend depth + production hardening.
6. **SAAS-08** constrained AI assistance only after deterministic and governance layers are stable.

## 4) Agent + skill operating policy
- **Explore** first for discovery on each non-trivial ticket.
- **Plan** second to define implementation and acceptance checks.
- **general-purpose** for build/refactor execution.
- Mandatory **code-review** before every build-ticket commit.
- Mandatory **security-review** for auth, tenancy, payments, uploads, webhooks.
- Mandatory **run/verify** before merge for user-visible/API behavior.
- Deterministic engine remains authoritative; AI/UI may explain but not override.

## 5) Minimal skill clone set to place in `.claude` now
Clone only what is needed for immediate SAAS-01 delivery:
- `code-review`
- `saas-multitenancy`
- `saas-auth`
- `saas-api`
- `saas-audit`
- `saas-frontend`
- `security-review`
- `run`
- `verify`

Defer later-epic skills until each epic starts.
