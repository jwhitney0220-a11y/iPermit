# ADR-0003: API Contract & Surface Design

- **Status:** Proposed (merging this PR constitutes sign-off)
- **Date:** 2026-05-25
- **Deciders:** Product owner, engineering
- **Supersedes:** none
- **Related:** [`/AGENTS.md`](../../AGENTS.md) (*Liability Strategy*, *Permit Confidence Tiers*, *MVP Functional Scope*, *GIS Strategy*, *Technical Philosophy*), [`ADR-0001`](./adr-0001-tech-stack.md), [`ADR-0002`](./adr-0002-auth-rbac-tenant-isolation.md), [`docs/specs/explainability.md`](../specs/explainability.md) (T00-05), [`docs/specs/temporal-versioning.md`](../specs/temporal-versioning.md) (T00-03), roadmap T01-15 (this ticket), T01-11 (shared schema packages), T03-02 (rules engine), T05-01 (GIS engine), T07-01 (permit matrix generator), T07-04 (deliverables export), T06-02 (intake), T01-04 (audit log)

> ADRs are immutable once accepted. To change a decision, write a new ADR that
> supersedes this one rather than editing this file.

---

## Context

ADR-0001 fixed the stack (Python/FastAPI, TypeScript/React, PostgreSQL+PostGIS)
and named the API contract as *the boundary*: "the T01-15 API contract is the
boundary; clients are thin presentation layers." This ADR formalizes that
boundary before the services that sit on either side of it are built.

Four producers and consumers meet at this boundary:

- The **deterministic rules engine** (T03-02) — the source of truth for permit
  outputs and explanation records.
- The **GIS services** (T05-01) — jurisdiction/overlay detection from uploaded
  shapefile/KMZ, plus manual-entry fallback (AGENTS.md *GIS Intake Strategy*).
- The **frontend apps** (T06-01 consultant, T08-02 analyst) — thin clients that
  render, never compute, permit logic.
- The **export / deliverable layer** (T07-04) — Excel/PDF generation from the
  permit matrix.

Constraints inherited from AGENTS.md and the specs:

- **Advisory language is mandatory.** No user-facing permit output may omit
  confidence tier, citations, or advisory text (AGENTS.md *Liability Strategy*,
  *Roadmap Philosophy*). The API envelope must carry these on every permit
  output — they are not optional fields a client may forget to render.
- **The deterministic engine is the source of truth.** Clients hold no business
  logic; AI never overrides deterministic outputs. The contract therefore puts
  all permit reasoning on the server side of this line.
- **Reproducibility.** Every evaluation is keyed by `ruleset_version`
  (`content_hash`), pinned `evaluation_date`, and `inputs_hash` (T00-03 §5.2,
  T00-05 §5.13). The API must surface and accept these so a result is replayable
  and auditable (T01-04).
- **Schema-driven types.** ADR-0001 made the `docs/specs/schemas/*.schema.json`
  files canonical and codegen-driven (T01-11). The API uses generated request /
  response types; it does **not** hand-write duplicate shapes.

What this ADR decides: the **API style, the service boundary contracts, the
response envelope (including the mandatory advisory fields), the versioning
strategy, and the error/advisory structure**. What it defers: the detailed
permit-matrix rendering and export file formats (T07-01 / T07-04), the intake
form field registry (T06-02), and concrete endpoint paths/payloads (the first
service PRs, generated from the OpenAPI spec).

---

## Decision

### Style — REST over HTTP via FastAPI, OpenAPI as the published contract

iPermit exposes a **REST API** built with FastAPI, and the **generated OpenAPI
document is the published contract**. This is the natural fit given ADR-0001:
FastAPI emits OpenAPI from typed Pydantic models for free, so the contract stays
current with the code rather than drifting from a hand-maintained spec.

The OpenAPI document is a CI artifact (wired under T01-07) and the input to the
TypeScript client/type codegen the frontends consume (T01-11). One source, two
languages, no hand-written duplication — exactly the polyglot-coherence property
ADR-0001 relies on.

### Schema-driven contracts — canonical JSON Schemas, generated types

Request and response bodies for domain objects are driven by the canonical JSON
Schemas, not invented at the API layer:

| Domain object | Canonical schema | Produced by | Consumed by |
|---------------|------------------|-------------|-------------|
| Rule object | `rule-object.schema.json` (T00-01) | analysts / rules store | analyst portal, engine |
| Jurisdiction record | `jurisdiction-record.schema.json` (T00-02) | GIS / analysts | engine, intake, matrix |
| Permit explanation | `permit-explanation.schema.json` (T00-05) | rules engine | matrix, export, audit |

The API's request/response models **reference these generated types** (Pydantic on
the server, TypeScript on the client, both from T01-11 codegen). API-only shapes
— the envelope, pagination wrappers, error bodies — are defined once in the
shared schema package and code-generated the same way. The rule that ADR-0001
set ("neither language hand-writes the shapes") extends to the API surface.

### Service boundary contracts

The boundary formalizes four contracts. Each is a request shape in and a
response shape out; all reasoning stays server-side.

1. **Rules-engine evaluation contract (T03-02).**
   - *In:* a project-inputs object (intake fields + confirmed GIS overlays; field
     registry owned by T06-02) plus a pinned `evaluation_date` and
     `evaluation_mode` (`live` / `exploratory` / `replay`, per T00-03 §5.2).
   - *Out:* the evaluation result — a set of fired (and optionally `not_fired`)
     **permit explanation records** conforming to T00-05, plus the
     reproducibility triple (`ruleset_version.content_hash`, `inputs_hash`,
     `evaluation_date`) the audit log (T01-04) persists.
   - The engine never reads wall-clock time for evaluation; `evaluation_date` is
     always an explicit request parameter (T00-03 §4.1, T00-05 §6).

2. **GIS overlay-query contract (T05-01).**
   - *In:* an uploaded shapefile/KMZ reference, or manual jurisdiction entries
     (fallback per AGENTS.md *GIS Intake Strategy*).
   - *Out:* detected jurisdictions and spatial overlays (county / municipality /
     ETJ / watershed / FEMA / USACE / districts), each annotated with a
     `detection_source` (`gis_auto_detect`, `user_confirmed`, `user_override`,
     `user_input`) matching the explainability `jurisdiction_chain` enum
     (T00-05 §5.3). Every user edit to an auto-detected value is logged
     (AGENTS.md *GIS Intake Strategy*; audit hook to T01-04).

3. **Permit-matrix output contract (T07-01).** Defined at a high level here; the
   rendered file/layout is T07-01 / T07-04. The matrix response is the
   consultant-facing aggregation of the evaluation: an ordered set of likely
   permits, each carrying — non-negotiably — its confidence tier, citations,
   advisories, and the explanation record reference. Sequencing data (T00-04)
   rides alongside. See *Permit-matrix output contract* below.

4. **Export / deliverable contract (T07-04).** Takes a permit-matrix result
   reference and a format (`xlsx` / `pdf` / `json`) and returns a generated
   deliverable. The export layer renders the *same* advisory/citation/tier data
   the matrix carries — it never recomputes or strips it. No deliverable may omit
   advisory language (AGENTS.md *Roadmap Philosophy*).

### Response envelope — advisory fields are structural, not optional

Every permit-bearing response is wrapped in a standard envelope so the mandatory
liability fields cannot be accidentally dropped by a client:

```
{
  "data": <domain payload>,            // generated-type payload
  "meta": {
    "ruleset_version": { "content_hash": "...", "commit_sha": "...?" },
    "evaluation_date": "YYYY-MM-DD",
    "evaluation_mode": "live|exploratory|replay",
    "evaluation_id": "...",            // audit cross-reference (T01-04)
    "schema_version": "1.0.0"
  },
  "advisories": [ { "text": "...", "origin": "rule|engine|platform", "category": "..." } ],
  "warnings": [ ... ]                  // non-fatal advisory notices (see Errors)
}
```

Where `data` is or contains permit outputs, each permit output carries its own
`confidence` (tier + freshness), `citations[]`, and `advisories[]` copied from
the T00-05 explanation record — the envelope-level `advisories` carries the
standing platform disclaimer and request-scoped notices, not a replacement for
per-permit advisories. The standing platform advisory ("Advisory only; not a
legal determination...") from T00-05 §4.4 is **always** present at the envelope
level. A response containing permit outputs with zero advisories is a contract
violation and should fail the response-side schema check in CI (T01-07),
mirroring the engine's `minItems: 1` advisory constraint (T00-05 §4).

### Error and advisory response structure

Two distinct concepts, deliberately separated:

- **Errors** — the request failed (validation, auth, not-found, server fault).
  RFC-9457 *problem-details* shape: `{ type, title, status, detail, instance,
  errors?[] }`. HTTP status carries the class (4xx client, 5xx server). Auth and
  tenant-isolation failures (ADR-0002) surface as `401` / `403` and are written
  to the audit log when they concern privileged actions.
- **Advisories / warnings** — the request *succeeded* but the result carries
  uncertainty the consultant must see: a Tier 2/3 permit fired
  (`confidence_warning`), a citation URL was unreachable
  (`citation_url_unreachable`), a GIS overlay was partial
  (`partial_gis_overlap`), or source data is stale (`freshness_warning`). These
  are **never** HTTP errors — the call worked. They flow through the
  `advisories` / `warnings` arrays using the fixed T00-05 §4.3 categories and
  §5.9 engine signals. This separation is what keeps "the answer is uncertain"
  from being confused with "the request broke."

### API versioning strategy

- **URI major version prefix** (`/api/v1/...`). A new major version is cut only
  for a breaking change to a request/response contract. Major versions may run
  in parallel during a deprecation window.
- **Additive within a major version.** New optional fields, new endpoints, and
  new advisory categories/engine-signals (added only by amending T00-05) are
  non-breaking and ship without a version bump.
- **Domain `schema_version` is independent of the API version.** The envelope
  carries `schema_version` (e.g. the permit-explanation `1.0.0` from T00-05 §5.1).
  A domain schema can evolve under change control (T00-05 §12) without forcing an
  API major bump, and vice versa. Clients negotiate on both.
- **`ruleset_version` is not an API version.** It identifies *which regulations*
  produced a result (T00-03), orthogonal to the API and schema versions. All
  three appear in the envelope `meta`.

### What lives behind the boundary (and what does not)

- **Behind (server-only):** all rule evaluation, conflict resolution (T03-03),
  temporal selection (T00-03), confidence/freshness computation, explanation
  generation (T00-05), spatial computation (T05-01). Clients receive results,
  never inputs to recompute them.
- **At the boundary:** the four contracts above, the envelope, errors/advisories,
  auth (ADR-0002 — the API enforces role/tenant on every endpoint regardless of
  which client calls it).
- **In front (client-only):** rendering, tier badge styling, tooltip behavior,
  matrix table layout (T07-02), form widgets (T06-02). The contract gives clients
  integers and plain text; clients map them to pixels.

---

## Consequences

### Positive

- The OpenAPI-from-FastAPI contract is always current and feeds T01-11 codegen,
  giving end-to-end typed clients with no hand-maintained duplication.
- Advisory/citation/tier fields are structural in the envelope, so the AGENTS.md
  liability requirement is enforced by the contract and a CI schema check rather
  than by client discipline.
- Errors vs. advisories are cleanly separated: an uncertain-but-valid permit
  result is never an HTTP error, and a broken request never masquerades as an
  advisory.
- `ruleset_version` + `evaluation_date` + `inputs_hash` in the envelope make
  every response auditable and replayable (T00-03, T01-04) by construction.
- Thin clients (ADR-0001) stay thin: no permit logic crosses the boundary.

### Negative / costs

- A response-side schema/advisory check must exist in CI (T01-07) or a regression
  could ship a permit response missing advisories.
- Maintaining parallel major versions during deprecation has a cost; mitigated by
  keeping changes additive within a major version wherever possible.
- The envelope adds a small payload overhead on every response; accepted for the
  traceability guarantee it buys.

### Neutral / deferred

- Concrete endpoint paths, payload field names, pagination/cursor details → first
  service PRs, generated from the OpenAPI spec.
- Permit-matrix file layout and export formats (xlsx/pdf cell-level design) →
  T07-01 / T07-04.
- Intake field registry (`project.*`, `geometry.*`) → T06-02 / T02-02.
- Rate limiting, caching headers, idempotency keys → deployment / later.
- Internal service-to-service transport (REST vs. gRPC between rules-engine /
  gis-engine / API) → deployment design; this ADR governs the *external* surface.

---

## Alternatives Considered

### GraphQL

A single typed graph endpoint with client-selected fields. **Rejected** as the
primary surface: FastAPI gives REST + OpenAPI essentially for free (ADR-0001),
the permit domain is request/response-shaped (evaluate a project → get a matrix)
rather than graph-traversal-shaped, and the mandatory advisory envelope is harder
to guarantee when clients select arbitrary field subsets (a client could select a
permit's name but omit its advisories — exactly what the liability strategy
forbids). GraphQL remains reconsiderable for a future read-heavy analyst
exploration surface, but not for the permit-output contract.

### gRPC / protobuf as the external contract

Strong typing and performance. **Rejected** for the external/browser surface:
poor browser ergonomics, and JSON Schema (not protobuf) is already the canonical
type source (ADR-0001). gRPC remains a reasonable option for *internal*
service-to-service calls and is deferred to deployment design, not this ADR.

### HTTP status codes carrying advisory state

Encode "result is uncertain" in a non-2xx status (e.g. `203`). **Rejected**:
conflates "the answer is low-confidence" with "the request had a problem," breaks
client error-handling conventions, and cannot carry the structured, multi-entry
advisory list the liability strategy requires. Advisories belong in the body.

### Hand-written API types separate from the JSON Schemas

Let the API define its own DTOs. **Rejected** outright: it reintroduces the
client/server drift ADR-0001 eliminated and would let the API's notion of a
permit explanation diverge from T00-05's canonical schema.

---

## Open Questions (do not block this ADR)

- Whether `not_fired` (negative) explanations are exposed eagerly or on-demand at
  the API layer — depends on the engine emission policy (T03-05 / T00-05 §7).
- Async evaluation (long-running GIS jobs) response pattern — synchronous vs.
  job-handle + poll/webhook — to be decided against real GIS latency (T05-01).
- Internal transport between services (REST vs. gRPC) — deployment design.
- Pagination/filtering conventions for analyst-facing list endpoints (rules,
  jurisdictions, feedback queue) — first analyst-portal service PR (T08-02).
