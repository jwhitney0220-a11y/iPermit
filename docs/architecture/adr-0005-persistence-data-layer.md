# ADR-0005: Persistence & Data Layer

- **Status:** Proposed (merging this PR constitutes sign-off)
- **Date:** 2026-05-25
- **Deciders:** Product owner, engineering
- **Supersedes:** none
- **Related:** [`ADR-0001`](./adr-0001-tech-stack.md) (PostgreSQL + PostGIS), [`ADR-0004`](./adr-0004-audit-logging.md), [`docs/operations/postgis-planning.md`](../operations/postgis-planning.md) (T01-16), [`docs/operations/environments.md`](../operations/environments.md) (T01-08), roadmap T02-01 (this ticket) and EPIC-02 generally

> ADRs are immutable once accepted. To change a decision, write a new ADR that
> supersedes this one rather than editing this file.

---

## Context

EPIC-02 builds the regulatory-intelligence data layer (jurisdictions, regulatory
schema, source tracking, freshness). ADR-0001 fixed PostgreSQL 16 + PostGIS as
the engine but did not choose an ORM, a migration tool, or where shared database
code lives. T02-01 (the jurisdiction hierarchy DB) is the first ticket that
needs all three, so they are decided here once for all of EPIC-02+.

## Decision

### ORM — SQLAlchemy 2.0 (typed)

Mature, the de-facto Python standard, first-class PostgreSQL + PostGIS support
(via GeoAlchemy2 when spatial columns arrive in EPIC-05), and 2.0's typed
`Mapped[...]` models fit the Maintainability/readability priorities. Models stay
small and declarative.

### Migrations — Alembic

The standard SQLAlchemy companion. `migrations/env.py` binds to the shared
`Base.metadata` and resolves the database URL from `DATABASE_URL` (T01-08), so
the same migrations run against local SQLite and managed PostgreSQL. The initial
migration creates the jurisdiction tables; every schema change ships as a
reviewed migration (no implicit `create_all` in production).

### Shared persistence package — `packages/persistence`

A new package `ipermit_persistence` owns the single declarative `Base`
(one `MetaData` with a deterministic constraint-naming convention) and the
engine/session factories. All domain model packages (`jurisdiction-models`,
and the EPIC-02 regulatory/source packages to come) import this `Base` so the
whole schema is visible to Alembic autogenerate and `create_all`.

### Portability — SQLite for tests, PostgreSQL for real

Models avoid backend-specific column types on the non-spatial path: lineage
arrays (`replaced_by`/`replaced_from`) use the portable `JSON` type, and enums
use `Enum(..., native_enum=False)` (VARCHAR + CHECK) so the identical schema
builds on SQLite (unit tests, CI — no PostgreSQL needed yet) and PostgreSQL
(staging/production). Spatial columns are deferred to EPIC-05, where the test
matrix gains a PostGIS service container (per the T01-16 plan).

### Validation at the boundary

Records are validated against their canonical JSON Schema (EPIC-00) **before**
they enter the database (e.g. `add_record` validates against the T00-08
jurisdiction-record schema). The database is never the place a malformed record
is first caught.

## Consequences

### Positive

- One ORM/migration stack for all of EPIC-02+; one shared `Base`/metadata.
- SQLite-portable models keep unit tests fast and CI free of a database service
  until spatial work genuinely needs one.
- JSON-Schema-at-the-boundary keeps the DB consistent with the EPIC-00 specs.

### Negative / costs

- Two SQL dialects in play (SQLite for tests, PostgreSQL for real). Mitigated by
  avoiding backend-specific types off the spatial path; spatial behavior must be
  tested against PostGIS (EPIC-05), not SQLite.
- `Enum(native_enum=False)` stores strings; the enum set lives in code + the
  JSON Schema rather than a native PG type. Acceptable — the schema is the
  source of truth and migrations stay simple.

### Neutral / deferred

- GeoAlchemy2 / PostGIS column types → EPIC-05 (T05-01).
- Connection pooling, read replicas → performance work.
- Per-package installable `pyproject.toml` packaging → future DX work; today
  packages are imported via path (tests use `tests/conftest.py`).

## Alternatives Considered

- **Django ORM** — rejected: pulls in the Django framework; ADR-0001 chose
  FastAPI, and Django's ORM is awkward outside Django.
- **Raw SQL / query builder (e.g. `databases` + hand-written SQL)** — rejected:
  more boilerplate and weaker typing than SQLAlchemy 2.0; harder to keep models
  aligned with the EPIC-00 schemas.
- **No migration tool (`create_all` only)** — rejected: unsafe for production
  schema evolution and incompatible with the audit/reproducibility posture
  (ADR-0004). Alembic gives reviewable, reversible schema changes.

## Open Questions (do not block this ADR)

- GeoAlchemy2 adoption details and the PostGIS CI service container → EPIC-05.
- Whether to add per-package `pyproject.toml` packaging → future DX ticket.
