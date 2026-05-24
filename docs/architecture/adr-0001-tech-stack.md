# ADR-0001: Technology Stack

- **Status:** Proposed (merging this PR constitutes sign-off)
- **Date:** 2026-05-24
- **Deciders:** Product owner, engineering
- **Supersedes:** none
- **Related:** [`/AGENTS.md`](../../AGENTS.md), roadmap EPIC-01 (T01-01, T01-05, T01-15, T01-16), EPIC-05 (T05-01), EPIC-09

> ADRs are immutable once accepted. To change a decision, write a new ADR that
> supersedes this one rather than editing this file.

---

## Context

EPIC-00 defined the deterministic foundation (rule object, jurisdiction ontology,
temporal versioning, explainability, benchmarks) without committing to an
implementation stack. EPIC-01 (repository bootstrap, CI, linters, IaC, auth) is
the first epic that produces real code and therefore needs a stack decision.

AGENTS.md does not pin a language. The constraints it *does* impose:

- **Priority order:** Maintainability → Explainability → Traceability → Scalability → Automation → UI polish.
- **Engineering standards:** functions under 60 lines, readability over cleverness, explicit logic.
- **Competitive moats** (priority order): regulatory intelligence database, workflow sequencing engine, historical permitting knowledge, enterprise workflow integration, AI tooling. AI is explicitly *not* the primary moat.
- **GIS** (EPIC-05): shapefile/KMZ ingestion, PostGIS or equivalent, county/ETJ/watershed/FEMA/USACE overlays.
- **AI** (EPIC-09): document extraction, constrained and advisory only.
- **Deterministic rules engine remains the source of truth.** Clients must not hold business logic.
- **Native iOS field app is explicitly deferred** post-PMF.
- Architecture must be **state-scalable** beyond Texas.

The key architectural observation: the product's value (rules engine, GIS overlay
detection, permit-matrix generation, explanation records) lives **server-side**.
The T01-15 API contract is the boundary; clients are thin presentation layers.
This makes the **backend language the high-stakes decision** and client languages
comparatively cheap and reversible.

---

## Decision

### Backend services — Python 3.11+ with FastAPI

Applies to `services/rules-engine`, `services/gis-engine`, `services/ai-assistant`,
`services/regulatory-monitor`.

Rationale:

- **Geospatial** is a core moat and is markedly stronger in Python: `shapely`,
  `geopandas`, `fiona`/`pyogrio` (shapefile + KMZ parsing), `pyproj`, and mature
  PostGIS workflows. Node's server-side geospatial story (GDAL bindings) is
  comparatively painful.
- **AI document extraction** (EPIC-09) is Python-first across the ecosystem.
- **The declarative rules engine** benefits from Python's readability, which
  directly serves the Maintainability/Explainability priorities.
- **Continuity:** the EPIC-00 schemas are already validated with Python +
  `jsonschema`. Pydantic v2 models map cleanly onto the JSON Schemas we wrote.
- FastAPI gives typed request/response models, automatic OpenAPI generation
  (feeds the T01-15 API contract), and async I/O without ceremony.

### Database — PostgreSQL 16 + PostGIS

Satisfies AGENTS.md "PostGIS or equivalent." Spatial planning is T01-16; spatial
infrastructure stand-up is T05-01. PostgreSQL also serves the relational
rule/jurisdiction/audit data. Single engine reduces operational surface.

### Shared schemas — JSON Schema as single source of truth

The `docs/specs/schemas/*.schema.json` files (rule object, jurisdiction record,
permit explanation, benchmark project) remain canonical. Generate:

- **Pydantic models** for the Python services.
- **TypeScript types** for the frontends (e.g. `json-schema-to-typescript`).

Neither language hand-writes the shapes. This is what keeps a polyglot stack
coherent and prevents drift between client and server. Formalized under T01-11
(shared schema packages).

### Web frontend — TypeScript + React

Applies to `apps/web` (consultant) and `apps/analyst-portal` (internal).

Rationale:

- Deepest ecosystem for the UI iPermit needs: permit-matrix tables, Excel/PDF
  export (T07-04), and lightweight map overlays via MapLibre GL / Leaflet (EPIC-05).
- TypeScript's type safety aligns with the Maintainability priority and consumes
  the generated schema types directly.
- Two apps share a component library; the analyst portal is role-gated (T01-14).

Framework specifics (Vite SPA vs. Next.js, component library, state management)
are deferred to T06-01 (consultant shell) and T08-02 (analyst shell) — this ADR
commits only to the language and React.

### Future iOS app — React Native (lean), decision deferred

The native iOS field app is deferred per AGENTS.md. When it is picked up:

- **Default to React Native** to reuse TypeScript talent, the generated schema
  types, and the API client.
- **Exception:** if the field app requires heavy offline-first maps and
  aggressive GPS/camera document capture, native Swift/SwiftUI is the better
  experience at the cost of a second codebase. Make that call against real
  field requirements, not now.

Either way, business logic stays server-side, so the mobile choice remains a UI
project rather than a rewrite.

---

## Consequences

### Positive

- Backend language matches the two hardest problem domains (GIS, AI) and the
  readability priority.
- JSON-Schema-driven types give end-to-end type safety across a polyglot stack
  without hand-maintained duplication.
- Thin clients keep web and future mobile decisions cheap and reversible.
- FastAPI's OpenAPI output gives T01-15 a generated, always-current contract.

### Negative / costs

- **Polyglot (Python + TypeScript)** means two toolchains, two CI lanes, two sets
  of linters/formatters, and engineers who can context-switch. Accepted because
  the moats justify Python on the backend.
- A schema-codegen step must exist in CI (T01-07) or types drift.
- Python async + geospatial CPU work needs care (worker pools / offloading) to
  avoid blocking the event loop; noted for T03-02 / T05-01.

### Neutral / deferred

- Specific frontend framework, build tool, and component library → T06-01 / T08-02.
- ORM/migration tooling (e.g. SQLAlchemy + Alembic) → T01-09 / T02-01.
- Background job/queue technology (for regulatory-monitor, freshness scans) → later.

---

## Alternatives Considered

### All-TypeScript (Node backend + React + React Native)

One language end to end, maximal code sharing, natural React Native path.
**Rejected** because server-side geospatial (shapefile/KMZ, GDAL, PostGIS) and AI
document extraction are materially weaker in Node, and those are core
differentiators (EPIC-05, EPIC-09) — not peripheral features. The single-language
savings did not outweigh giving up the strongest libraries for the actual moats.

### Go backend

Fast, simple, great for services. **Rejected** as the primary backend: weaker
geospatial and AI ecosystems, and more verbose for the declarative,
readability-first rules engine. Remains a reasonable future choice for an isolated
high-throughput service if one is ever needed.

### Flutter (Dart) for mobile

Strong cross-platform UI. **Rejected** as the default because it introduces a
third language (Dart) with no reuse of the web stack's TypeScript talent or
generated types. Reconsider only if a future ADR also moves the web app off React.

---

## Open Questions (do not block this ADR)

- Frontend framework choice (Vite vs. Next.js) — T06-01.
- Managed PostGIS (e.g. cloud SQL with PostGIS) vs. self-hosted — T01-16.
- Schema → type codegen tooling selection and CI wiring — T01-07 / T01-11.
