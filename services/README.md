# services/

Backend services. Python 3.11+ with FastAPI per [ADR-0001](../docs/architecture/adr-0001-tech-stack.md).

| Service | Responsibility | Built by |
|---------|----------------|----------|
| [`rules-engine/`](./rules-engine) | Deterministic permit evaluation: declarative rule parsing, evaluation, conflict resolution, sequencing, explainability, known-unknown detection. **The source of truth.** | EPIC-03 (T03-01–T03-06) |
| [`gis-engine/`](./gis-engine) | Lightweight spatial intelligence: shapefile/KMZ ingestion, jurisdiction & overlay detection. | EPIC-05 (T05-01–T05-06) |
| [`ai-assistant/`](./ai-assistant) | Constrained, advisory AI: document extraction, proposal drafting, workflow summarization. Never overrides deterministic output. | EPIC-09 (T09-01–T09-04) |
| [`regulatory-monitor/`](./regulatory-monitor) | Source freshness scoring, expiration monitoring, AI-assisted change flagging (all analyst-gated). | T02-07, T08-03, T09-04 |

## Boundaries

- The **deterministic rules engine remains the source of truth** (AGENTS.md). AI
  services produce advisory output only and must not override it.
- Services expose typed contracts per T01-15. Request/response models are
  generated from the canonical JSON Schemas (`packages/shared-schemas`, T01-11).
- Functions stay under 60 lines per AGENTS.md engineering standards (enforced by
  T01-02 linters).

## Status

Directory scaffold only. Per-service Python packaging, dependency management, and
test runners are wired in T01-12; CI in T01-07.
