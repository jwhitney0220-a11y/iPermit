# iPermit SaaS v1 Build Review (as of May 26, 2026)

## Scope
This review captures what the most recent implementation agent changed and maps current repository readiness to the redefined SaaS roadmap (`saas-v1`).

## Latest implementation reviewed
- Commit: `eba3d22`
- Title: `T05-01/T05-02: GIS spatial foundation and shapefile/KMZ ingestion`

### Files changed in `eba3d22`
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

### Capability impact from that change
- Added GIS ingestion primitives for shapefile/KML parsing.
- Added normalized footprint handling for downstream workflows.
- Added geometry helper logic and storage-facing helpers.
- Added targeted tests across ingest/geometry/normalization/store paths.

## SaaS-v1 readiness snapshot

### Already in place or materially started
- Deterministic rules-engine and evaluation internals.
- Benchmark project regression framework.
- Regulatory model primitives (temporal/freshness/confidence).
- GIS ingestion foundation and focused test coverage.

### Gaps to close for SaaS productization
- Tenancy persistence model + tenant isolation hardening (RLS + app scoping).
- Auth stack (AuthenticatedIdentity, password/JWT, RBAC/roles).
- FastAPI SaaS envelope + RFC-9457 problem detail responses.
- Consultant app flow (login -> intake -> evaluate -> matrix).
- Audit event chain (minimal first, then full hash-chain).
- Billing/metering/webhooks + entitlement gating.
- Admin/analyst operations portal and publication workflow.
- Deploy/observability hardening.

## Recommended execution sequence
1. SAAS-01 (S01-01 through S01-07) as a thin vertical spine.
2. SAAS-02 productization depth (RBAC expansion, audit chain, revisions, exports, feedback queue).
3. SAAS-03 billing only after authz/tenancy controls are stable.
4. SAAS-04 and SAAS-05 app depth once SAAS-01 APIs stabilize.
5. SAAS-06 and SAAS-07 spatial backend depth + production hardening.
6. SAAS-08 constrained AI features only after deterministic governance layers are mature.

## Agent and skill policy (execution governance)
- Use **Explore** before any non-trivial build ticket.
- Use **Plan** to define implementation and acceptance criteria.
- Use **general-purpose** for implementation work.
- Run **code-review** on each build ticket before commit.
- Run **security-review** for auth, tenancy, payments, uploads, webhooks.
- Run **run/verify** checks before merge when behavior is user/API visible.
- Deterministic rules engine remains source of truth; AI/UI must not override.
