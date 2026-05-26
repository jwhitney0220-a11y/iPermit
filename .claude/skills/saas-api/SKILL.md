---
name: saas-api
description: >
  Build iPermit FastAPI routers, request/response models, and the standard
  response envelope. Use for any HTTP API ticket (S01-03, S01-04, S02-03/04/05,
  S05-02/03, S06-02). Enforces ADR-0003 API contract + RFC-9457 problem details.
---

# saas-api — FastAPI surface for iPermit

iPermit backend is **Python 3.11 + FastAPI** (ADR-0001). The API boundary and
contract are ADR-0003 (`docs/architecture/adr-0003-api-contract-and-surface.md`).
Read it before building. The deterministic engine (`ipermit_engine`) and GIS
(`ipermit_gis`) are the source of truth — endpoints orchestrate them, never
re-implement permit logic.

## Conventions

- **Response envelope** (every success): `{ "data": <payload>, "meta": {...},
  "advisories": [...], "warnings": [...] }`. Permit outputs MUST carry advisory
  language, confidence tier, and citations (AGENTS.md liability strategy) — surface
  them in `advisories`, never as bare claims.
- **Errors: RFC-9457** problem+json (`type`, `title`, `status`, `detail`,
  `instance`). One FastAPI exception handler maps domain errors → problem details.
  Introduce this in S01-03 and record it as **ADR-0006**.
- **Schemas from the source of truth**: request/response models reuse the
  Pydantic models generated from `docs/specs/schemas/*` (`packages/shared-schemas`)
  — do not hand-redefine rule/jurisdiction/explanation shapes.
- **Versioning**: prefix routes `/api/v1`. Additive changes only within a version.
- **Tenancy + auth**: every data route is tenant-scoped (saas-multitenancy) and
  auth-gated (saas-auth); take the `AuthenticatedIdentity` as a dependency.
- **Functions < 60 lines** (AGENTS.md); routers thin, logic in services.

## Build checklist

1. Explore the existing engine/GIS API you're wrapping; Plan the routes.
2. Define Pydantic request/response models (reuse generated schemas).
3. Implement router; inject auth + tenant scope; return the envelope.
4. Map errors to RFC-9457.
5. Tests: happy path, validation error (→ problem detail), authz/tenant isolation.
6. `code-review` the diff; `run`/`verify` the endpoint; commit.

## Reference

ADR-0003; open-saas server patterns are Node — translate intent, not code.
