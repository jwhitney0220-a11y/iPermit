# ADR-0006: Public API Service Boundary (`services/api`)

- **Status:** Proposed (merging this PR constitutes sign-off)
- **Date:** 2026-05-26
- **Deciders:** Product owner, engineering
- **Supersedes:** none
- **Related:** [`ADR-0001`](./adr-0001-tech-stack.md), [`ADR-0002`](./adr-0002-auth-rbac-tenant-isolation.md), [`ADR-0003`](./adr-0003-api-contract-and-surface.md), [`ADR-0004`](./adr-0004-audit-logging.md), [`ADR-0005`](./adr-0005-persistence-data-layer.md), `docs/saas-roadmap.json` (SAAS-01), roadmap T01-15

> ADRs are immutable once accepted. To change a decision, write a new ADR that
> supersedes this one rather than editing this file.

---

## Context

ADR-0003 fixed the *external contract* (REST, OpenAPI, the response envelope) but
not *where it is served from*. The four ADR-0003 boundary contracts span three
existing libraries: the rules engine (`services/rules-engine`), the GIS
confirmation layer (`services/gis-engine`), and the persistence/tenancy packages.
A single permit evaluation composes all of them: confirm GIS → build engine
context → `simulate_project` → `build_permit_matrix` → persist + audit.

The question is whether to bolt the HTTP surface onto one existing library
(e.g. the rules engine) or stand up a dedicated composing service.

## Decision

Introduce **`services/api`** (Python package `ipermit_api`) as a dedicated
**public API / backend-for-frontend (BFF)** service. It owns the HTTP surface,
auth, the response envelope, tenant scoping, and orchestration; it composes the
deterministic libraries but contains **no permit business logic** (that stays in
the engine — the source of truth, AGENTS.md). It is the only tier that:

- terminates auth and resolves `AuthenticatedIdentity` (ADR-0002),
- sets the Postgres RLS tenant GUC and enforces app-layer tenant scope (ADR-0002),
- assembles the `{data, meta, advisories, warnings}` envelope and RFC-9457 errors
  (ADR-0003),
- writes the hash-chained audit log on privileged actions (ADR-0004).

The deterministic libraries remain pure and DB-free; `services/api` depends on
them, never the reverse.

## Consequences

### Positive

- Keeps the rules/GIS engines pure and independently testable; HTTP concerns do
  not leak into the source of truth.
- One place owns auth, tenancy, the envelope, and audit — the cross-cutting
  guarantees ADR-0002/0003/0004 require — instead of scattering them.
- Matches the thin-client model (ADR-0001): all reasoning stays server-side of
  this one boundary.

### Negative / costs

- A new deployable service and its dependency set (FastAPI, uvicorn, PyJWT,
  bcrypt) — the first runtime deps beyond the tooling stack.
- One more package on the monorepo `sys.path` wiring (alembic/conftest already
  follow this pattern for the model packages).

### Neutral / deferred

- Internal service-to-service transport (the engines stay in-process libraries
  for now; a network split is a later deployment decision — ADR-0003 open question).
- Whether the analyst portal gets its own BFF or shares this one → SAAS-05.
