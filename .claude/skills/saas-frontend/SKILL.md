---
name: saas-frontend
description: Use when building or changing the iPermit React/TypeScript SPA(s) — apps/web (consultant) or apps/analyst-portal (internal): routing, forms, data fetching, auth-gated pages, or the permit-matrix UI.
---

# saas-frontend — React/TS SPA

**Stack:** Vite + React + TypeScript (ADR-0001; the devcontainer forwards port 5173).

## Conventions
- Reuse the generated types in `packages/shared-schemas/typescript`. Generate the API client from the FastAPI OpenAPI document — never hand-duplicate response shapes.
- ESLint extends the root `.eslintrc.cjs` (`max-lines-per-function: 60`); Prettier from root `.prettierrc.json`.
- Auth-gated routes hold the bearer token; render the API envelope (`data` / `advisories` / `warnings`).
- **Permit-matrix UI MUST surface, per permit: confidence tier, source citations, and advisories** (liability framework). Never present output as a guarantee.

## Reference
open-saas `template/app/src/client`, `src/auth`, `src/landing-page` (Wasp — UX/structure pattern only).

## Scope discipline
Consultant app = `apps/web`; internal analyst/admin = `apps/analyst-portal` (use the **saas-admin-portal** skill there).

## Verify
Use the **run** skill: `npm run build` then `vite` dev (5173) against the API (8000); walk the flow manually. Add component render tests where practical.
