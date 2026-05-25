# iPermit
All in one permit helper

## Documentation

- [`AGENTS.md`](./AGENTS.md) — Strategic product identity, governance, and engineering standards. Authoritative guardrails for all work.
- [`docs/roadmap.json`](./docs/roadmap.json) — Structured development roadmap (machine-readable source of truth).
- [`docs/roadmap.md`](./docs/roadmap.md) — Human-readable roadmap view.
- [`docs/specs/`](./docs/specs) — Design specifications (EPIC-00): rule object, jurisdiction ontology & naming, temporal versioning, dependency sequencing, explainability, benchmarks, analyst SOP.
- [`docs/architecture/`](./docs/architecture) — Architecture Decision Records. See [ADR-0001](./docs/architecture/adr-0001-tech-stack.md) for the technology stack.
- [`docs/engineering-handbook/`](./docs/engineering-handbook) — Engineering handbook (onboarding, standards, repository strategy).

## Repository layout

Monorepo. Stack per [ADR-0001](./docs/architecture/adr-0001-tech-stack.md): Python/FastAPI services, TypeScript/React apps, PostgreSQL + PostGIS.

| Path | Contents |
|------|----------|
| [`apps/`](./apps) | User-facing React apps: `web` (consultant), `analyst-portal` (internal). |
| [`services/`](./services) | Python/FastAPI backend: `rules-engine`, `gis-engine`, `ai-assistant`, `regulatory-monitor`. |
| [`packages/`](./packages) | Shared libraries: `shared-schemas`, `jurisdiction-models`, `rule-definitions`, `benchmark-projects`. |
| [`rules/`](./rules) | Declarative rule store by lifecycle: `draft`, `published`, `effective`, `archived`. |
| [`infrastructure/`](./infrastructure) | Infrastructure-as-Code (T01-09). |
| [`scripts/`](./scripts) | Developer and operational scripts. |
| [`tests/`](./tests) | Cross-cutting and integration tests. |
| [`docs/`](./docs) | Specs, ADRs, roadmap, engineering handbook. |

Most directories are scaffolds today; each carries a `README.md` naming the ticket that builds it out.
