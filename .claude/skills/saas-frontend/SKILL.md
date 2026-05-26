---
name: saas-frontend
description: >
  Build the iPermit consultant/analyst web UI — React + TypeScript (Vite) SPA,
  auth-gated routes, OpenAPI-typed API client. Use for frontend tickets (S01-06,
  S04-01/02, S05-01/03). Grounded in ADR-0001; open-saas src/client is the pattern.
---

# saas-frontend — React + TypeScript SPA

iPermit web is **React + TypeScript on Vite** (ADR-0001), under `apps/web`
(consultant) and `apps/analyst-portal` (internal). open-saas `client/` (in
`.claude/references/open-saas/client`) is a Wasp/Node pattern reference — reuse
component/layout ideas, not the Wasp wiring.

## Conventions

- **Thin client**: no permitting business logic in the browser. The deterministic
  engine + API are the source of truth; the SPA renders matrices, advisories,
  citations, confidence tiers, and uncertainty flags exactly as the API returns
  them (never fabricate or soften advisory language).
- **Typed API client**: generate the client/types from the FastAPI OpenAPI spec
  (saas-api) so client and server cannot drift — same single-source-of-truth
  discipline as the schema codegen.
- **Auth-gated routing**: a route guard reads the session (saas-auth); unauth →
  login. Role-gated views for analyst/admin (S05). Store tokens securely; refresh
  flow handled centrally.
- **Response envelope**: render `data`, surface `advisories`/`warnings`
  prominently; map RFC-9457 problem details to user-facing errors.
- **Components**: a shared component lib across the two apps; shadcn/ui-style
  primitives (the open-saas `client/components/ui` patterns are a useful starting
  point).

## Build checklist

1. Vite + React + TS app scaffold (S01-06 / S04-01); routing + auth guard.
2. Generated API client from OpenAPI; env-based API base URL.
3. The flow for the ticket (e.g. login → intake form → evaluate → permit matrix).
4. Render advisories/citations/tier/uncertainty faithfully.
5. `run` the Vite dev server + FastAPI and `verify` the flow in the browser;
   code-review; commit. (UI correctness needs real browser verification, not just
   type-check.)

## Reference

ADR-0001, ADR-0003 (envelope); `.claude/references/open-saas/client` (pattern only).
