# apps/web

Consultant-facing SPA (Vite + React + TypeScript) — the SAAS-01 thin vertical:
**login → tenant-scoped project → intake → explainable permit matrix**. A thin
presentation layer (ADR-0001): it holds no permit logic and renders the
`{data, meta, advisories, warnings}` envelope from `services/api` (ADR-0003).
The manual jurisdiction/overlay entry is the GIS fallback (AGENTS.md *GIS Intake
Strategy*) until real detection lands (SAAS-06).

## Develop

```bash
npm install
npm run dev      # http://127.0.0.1:5173 ; /api is proxied to 127.0.0.1:8000
npm run build    # tsc --noEmit && vite build
```

Run the API (`uvicorn ipermit_api.app:app`) on :8000 alongside it. Set
`VITE_API_BASE` to call a non-proxied API origin.

## Layout

- `src/api.ts` — typed fetch client (bearer token, RFC-9457 errors).
- `src/types.ts` — contract types mirroring the envelope + permit matrix.
- `src/fields.ts` / `src/intake.ts` — intake field registry + request builder
  (includes a federal-nexus prefill for quick manual walkthroughs).
- `src/components/` — `Login`, `EvaluationScreen`, `IntakeForm`, `PermitMatrix`.
