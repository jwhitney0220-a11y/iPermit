---
name: saas-multitenancy
description: >
  Add and enforce tenant isolation for iPermit (tenant_id scoping + Postgres
  row-level security). Use for tenancy/persistence tickets (S01-01) and whenever
  adding a tenant-owned table or query. Grounded in ADR-0002.
---

# saas-multitenancy — tenant isolation

iPermit is multi-tenant (individual consultants + enterprise teams) per ADR-0002
(`docs/architecture/adr-0002-auth-rbac-tenant-isolation.md`). Stack: SQLAlchemy
2.0 + Postgres (ADR-0005). **Defense in depth: app-layer scoping AND DB row-level
security.**

## Conventions

- Every tenant-owned table has a non-null `tenant_id` FK to `tenant`. Projects,
  evaluations, audit rows, uploads, feedback — all tenant-scoped.
- **App layer**: a single tenant-aware session/repository helper injects
  `WHERE tenant_id = :current_tenant` on every query; never hand-write a tenant
  filter per call site (that's how leaks happen). Cross-tenant access is impossible
  through the normal data path.
- **DB layer (Postgres prod)**: `ENABLE ROW LEVEL SECURITY` + a policy keyed on a
  session GUC (e.g. `SET app.tenant_id`). Documented + applied via Alembic. RLS is
  the backstop if app scoping is ever bypassed.
- **Tests (SQLite)**: RLS isn't available on SQLite, so unit-test the app-layer
  scoping (a query from tenant A never returns tenant B rows); document that RLS is
  verified against Postgres (CI service / staging), mirroring the ADR-0005
  SQLite-for-tests pattern.
- Models inherit the shared `Base` (`ipermit_persistence`); migrations via Alembic.

## Build checklist

1. Tenant + membership models; `tenant_id` on owned tables; Alembic migration.
2. Tenant-aware session/repo helper (the only sanctioned data path).
3. RLS policies in the migration (Postgres) + docstring on the SQLite caveat.
4. Tests: scoping isolation (A cannot see B); FK integrity.
5. **security-review is mandatory** (tenancy). Then code-review, commit.

## Reference

ADR-0002, ADR-0005; open-saas has no RLS (Prisma) — use the Postgres-native pattern.
