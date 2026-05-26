# iPermit

Consultant-focused permitting intelligence and workflow platform for Texas utility and transmission infrastructure projects.

## Current planning docs

- `AGENTS.md` — product guardrails, liability language, and engineering standards.
- `docs/roadmap/saas-v1-review.md` — current SaaS-v1 build review and execution policy (updated 2026-05-26).
- `docs/roadmap/saas-v1-skills-needed.json` — current minimal skill/agent clone manifest for SaaS-v1 execution.
- `docs/architecture/` — ADRs (tech stack, tenancy/auth, API contract, audit logging, persistence).

## Monorepo layout

- `apps/` — consultant and analyst web apps.
- `services/` — backend services (rules-engine, gis-engine, ai-assistant, regulatory-monitor).
- `packages/` — shared schemas and domain libraries.
- `rules/` — rule lifecycle directories (`draft`, `published`, `effective`, `archived`).
- `docs/` — specifications, ADRs, and roadmap artifacts.
- `tests/` — test suites.
