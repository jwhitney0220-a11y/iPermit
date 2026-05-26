---
name: saas-audit
description: Use when writing or extending the append-only audit log — rule lifecycle events, permit evaluations, output corrections, feedback, or auth-significant events.
---

# saas-audit — immutable audit log

**Authority:** `docs/architecture/adr-0004-audit-logging.md`.

## Conventions (ADR-0004)
- Append-only PostgreSQL table(s); the application role has INSERT only — no UPDATE/DELETE on audit rows.
- Record shape: monotonic `id`, `occurred_at` (UTC), `actor`, `action`, `subject`, structured `payload`, `prev_hash`, `hash`. Each record hashes its content + the previous record's hash (tamper-evident chain).
- Corrections are **compensating new records** referencing the original — never in-place edits.
- Large geometry inputs are stored in object storage by hash and referenced, not inlined.

## What must be logged
Rule lifecycle transitions (draft→validated→reviewed→published→effective→archived→superseded) with reviewer attribution; every permit-matrix evaluation (inputs + `ruleset_version` hash + GIS inputs + output/explanation record ids); output corrections; feedback receipt/disposition; auth-significant events (role grants, tenant provisioning).

## Guardrails
Functions ≤ 60 lines. Test that the `hash`/`prev_hash` chain links across successive records. Never mutate or delete an audit row.
