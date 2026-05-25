# iPermit Documentation

Index of the `docs/` tree.

| Area | Contents |
|------|----------|
| [`architecture/`](./architecture) | Architecture Decision Records (ADRs). Start with [ADR-0001 (tech stack)](./architecture/adr-0001-tech-stack.md). |
| [`specs/`](./specs) | EPIC-00 design specifications: rule object, jurisdiction ontology & naming, temporal versioning, dependency sequencing, explainability, benchmarks, analyst SOP. JSON Schemas live in `specs/schemas/`. |
| [`engineering-handbook/`](./engineering-handbook) | Engineer onboarding: standards, repository strategy, rules-engine behavior, editing/testing/deployment procedures. |
| [`rules/`](./rules) | Rule-authoring guides (how to write and maintain rule objects). |
| [`gis/`](./gis) | GIS overlay and spatial-intake workflow documentation (EPIC-05). |
| [`operations/`](./operations) | Operational runbooks: environments, branching/release, spatial-infra planning. |
| [`analyst-sops/`](./analyst-sops) | Expanded regulatory-analyst procedures. The canonical SOP is [`specs/analyst-sop.md`](./specs/analyst-sop.md). |
| [`testing/`](./testing) | Testing and QA/QC documentation (EPIC-04). |
| [`roadmap.md`](./roadmap.md) / [`roadmap.json`](./roadmap.json) | Development roadmap (human-readable + machine-readable). |

Authoritative product guardrails live in the repo-root [`AGENTS.md`](../AGENTS.md).

This structure is established under ticket T01-10. Several subdirectories are
placeholders that later epics populate; each carries a README naming its owner.
