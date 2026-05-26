---
name: saas-multitenancy
description: Use when adding tenant isolation — tenant_id columns, PostgreSQL row-level security (RLS), tenant-scoped queries, or tenant provisioning.
---

# saas-multitenancy — tenant isolation

**Authority:** `docs/architecture/adr-0002-auth-rbac-tenant-isolation.md`.

## Conventions (ADR-0002) — two enforcement layers
1. **App-layer scoping:** every query against tenant-owned data filters by the request's `tenant_id`. This is the primary guard and the one tests assert (works on SQLite).
2. **Postgres RLS:** policies keyed on the session GUC `app.current_tenant_id`, set in the DB session dependency. Defense-in-depth; **Postgres-only** (no-ops on SQLite).

## Rules
- `tenant_id` FK on all tenant-owned rows: projects, evaluations, exports, feedback.
- Regulatory data (rules, jurisdictions) is **platform-global** — never tenant-scoped.
- Schema-per-tenant and database-per-tenant were rejected — do not introduce them.

## Guardrails
- **MANDATORY** security-review.
- Write a cross-tenant isolation test: a user in tenant A must not read tenant B's rows (assert on SQLite via app-layer scoping; add a Postgres-marked RLS test, skipped without a Postgres `DATABASE_URL`).
- Functions ≤ 60 lines. Models import the shared `ipermit_persistence.Base`.
