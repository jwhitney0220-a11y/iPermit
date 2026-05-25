# ADR-0004: Audit Logging Infrastructure

- **Status:** Proposed (merging this PR constitutes sign-off)
- **Date:** 2026-05-25
- **Deciders:** Product owner, engineering, regulatory operations lead
- **Supersedes:** none
- **Related:** [`/AGENTS.md`](../../AGENTS.md) (*Liability Strategy*, *Human Review Workflow*, *Data Governance*, *Temporal Versioning*), [`ADR-0001`](./adr-0001-tech-stack.md), [`ADR-0002`](./adr-0002-auth-rbac-tenant-isolation.md), [`ADR-0003`](./adr-0003-api-contract-and-surface.md), [`docs/specs/explainability.md`](../specs/explainability.md) (T00-05), [`docs/specs/temporal-versioning.md`](../specs/temporal-versioning.md) (T00-03), [`docs/specs/analyst-sop.md`](../specs/analyst-sop.md) (T00-09), roadmap T01-04 (this ticket), T08-04 (publication workflow), T08-06 (feedback queue), T04-05 (QA dashboard)

> ADRs are immutable once accepted. To change a decision, write a new ADR that
> supersedes this one rather than editing this file.

---

## Context

iPermit is advisory infrastructure for regulated work, and AGENTS.md ranks
Traceability third among technical priorities. Several already-accepted decisions
assume an audit substrate exists:

- **Temporal versioning (T00-03)** requires that a project's evaluation can be
  *replayed* against the exact ruleset version used at the time.
- **Explainability (T00-05)** defines an explanation record that must be
  reproducible byte-for-byte from `{inputs, ruleset_version, evaluation_date}`.
- **The analyst SOP (T00-09)** requires reviewer attribution and a change trail
  for every rule, and forbids mutating `effective`/`archived` rules in place.
- **The publication workflow (T08-04)** needs publication history and rollback.
- **The feedback queue (T08-06)** must link resolved feedback to the rule-change
  audit trail.

This ADR defines the audit-logging substrate those features write to. It is a
design decision, not an implementation — no service code exists yet.

## Decision

### 1. Append-only, immutable audit log

A single logical audit log, append-only. Records are never updated or deleted in
the normal course of operation. Corrections are new records that reference the
record they correct (compensating entries), never in-place edits. This mirrors
the rule lifecycle rule from T00-09 ("never mutate effective/archived in place").

### 2. What is logged

| Domain | Events |
|--------|--------|
| Rule lifecycle | draft created, validated, peer-reviewed, published, made effective, archived, superseded (ties to T08-04). |
| Reviewer actions | who reviewed/approved what, when (ties to T00-09, ADR-0002 roles). |
| Evaluations | every permit-matrix generation: project inputs, `ruleset_version` (commit SHA / content hash), GIS inputs, and the produced outputs + explanation record IDs (ties to T00-05, T00-03). |
| Output changes | regeneration or correction of a previously delivered matrix. |
| Feedback | consultant feedback received, analyst disposition (ties to T08-06). |
| Auth-significant events | role grants/changes, tenant provisioning (ties to ADR-0002). |

### 3. Record shape (design level)

Every record carries: a monotonic `id`, `occurred_at` (UTC), `actor`
(user/role/tenant or `system`), `action`, `subject` (e.g. `rule_id@version`,
`evaluation_id`), a structured `payload` (the before/after or the inputs/outputs
reference), and `prev_hash` + `hash` for tamper-evidence (each record hashes its
content plus the previous record's hash, forming a chain). The exact field
encoding is generated from a JSON Schema under T01-11, consistent with ADR-0003.

### 4. Storage

Append-only PostgreSQL table(s) (ADR-0001's single engine), with:

- `INSERT`-only application role; no `UPDATE`/`DELETE` granted to services.
- The hash chain (§3) makes silent tampering detectable even by a DB admin.
- Evaluation payloads may reference large inputs (uploaded geometry) stored in
  object storage by hash, rather than inlining them.
- Retention is indefinite for rule/evaluation history (reproducibility is the
  point); operational/auth events may have a finite retention set in
  implementation.

### 5. Relationship to reproducibility

The audit log is the record *that* an evaluation happened and with which ruleset
version; the explanation record (T00-05) is the detailed *why*. Together with the
immutable `rules/effective/` history (git) they let any past evaluation be
replayed (T00-03). The log stores the `ruleset_version` hash; it does not store a
copy of the rules (git already does, immutably).

## Consequences

### Positive

- Satisfies the Traceability priority and the reproducibility/attribution
  contracts that T00-03, T00-05, and T00-09 already assume.
- Hash-chained append-only storage gives tamper-evidence without a separate
  ledger technology.
- Single-engine (Postgres) keeps operational surface small (Maintainability).

### Negative / costs

- Append-only + indefinite retention grows unbounded; needs partitioning/archival
  strategy at scale (implementation concern).
- Hash chaining adds write-ordering constraints; high-volume evaluation logging
  must serialize per chain or shard chains by domain.
- Discipline required: no service may be granted `UPDATE`/`DELETE` on the log.

### Neutral / deferred

- Concrete table partitioning, retention windows, and chain-sharding → T01-04
  implementation.
- Whether evaluation logging is synchronous or via a queue → performance work.

## Alternatives Considered

### Application logging / log aggregator only (e.g. ship to a log service)

**Rejected** as the system of record: general log pipelines are lossy and
mutable, unsuitable for the reproducibility and attribution guarantees. A log
aggregator may still receive a copy for ops observability, but it is not the
audit substrate.

### Dedicated ledger / blockchain technology

**Rejected** as over-engineered for the threat model. A hash-chained append-only
Postgres table provides sufficient tamper-evidence without new infrastructure,
consistent with ADR-0001's single-engine choice.

### Event sourcing as the primary data model

**Rejected** as the system-wide model: it is a larger architectural commitment
than this ticket should make. The audit log is append-only and event-like, but
the operational data (rules, jurisdictions, projects) keeps conventional models.

## Open Questions (do not block this ADR)

- Partitioning and retention policy for high-volume evaluation events → T01-04 implementation.
- Sync vs. asynchronous evaluation logging → performance work / T03-02.
- Exposure of audit history in the analyst QA dashboard → T04-05.
