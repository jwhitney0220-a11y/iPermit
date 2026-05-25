# apps/

User-facing applications. Both are TypeScript + React per [ADR-0001](../docs/architecture/adr-0001-tech-stack.md).

| App | Audience | Built by | Notes |
|-----|----------|----------|-------|
| [`web/`](./web) | Consultants | T06-01 | Primary consultant-facing app: project intake, permit matrix, deliverables, history. |
| [`analyst-portal/`](./analyst-portal) | Regulatory analysts, platform admins | T08-02 | Internal app: rule review, QA/QC dashboards, publication workflows, rule-health monitoring. Role-gated via T01-14 RBAC. |

## Boundaries

Apps are **thin presentation layers**. They hold no permitting business logic —
all rule evaluation, GIS detection, permit-matrix generation, and explanation
records come from the backend services via the API contract (T01-15). This keeps
client choices reversible (see ADR-0001).

Shared UI components and the generated TypeScript types (from
`packages/shared-schemas`, T01-11) are consumed by both apps.

## Status

Directory scaffold only. Framework selection (Vite vs. Next.js), component
library, and build tooling are decided in T06-01 / T08-02 and wired in T01-12.
