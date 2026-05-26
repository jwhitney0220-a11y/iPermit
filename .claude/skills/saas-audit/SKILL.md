---
name: saas-audit
description: >
  Build iPermit's append-only, hash-chained audit log. Use for audit tickets
  (S01-05 minimal on evaluation, S02-02 full chain across events) and whenever a
  rule/permit/publication/auth event must be recorded. Grounded in ADR-0004.
---

# saas-audit — append-only hash-chained audit log

ADR-0004 (`docs/architecture/adr-0004-audit-logging.md`) is authoritative. The
audit log underpins the T00-03 replay and T00-05 reproducibility contracts and
T00-09 attribution. Stack: Postgres, append-only.

## Conventions

- **Append-only**: services get `INSERT` only — no `UPDATE`/`DELETE` grant on the
  audit table. Corrections are new compensating records that reference the prior
  one, never edits.
- **Record shape**: `id` (monotonic), `occurred_at` (UTC), `actor`
  (user/role/tenant or `system`), `action`, `subject` (e.g. `rule_id@version`,
  `evaluation_id`), structured `payload`, `tenant_id`, plus `prev_hash` + `hash`.
  Each record hashes its canonical content + the previous record's hash → a chain;
  silent tampering is detectable.
- **Evaluation logging (S01-05, minimal)**: on every permit evaluation record the
  project inputs reference, `ruleset_version` (content hash / commit SHA), and the
  produced outputs/explanation ids — enough to replay (T00-03/T00-05). Large
  inputs (geometry) referenced by hash, not inlined.
- **Full chain (S02-02)**: extend to rule lifecycle, reviewer actions, publication
  history, auth-significant events, feedback dispositions.
- **Determinism**: canonical JSON (sorted keys) before hashing so the chain is
  reproducible.

## Build checklist

1. Audit model (tenant-scoped, append-only); Alembic migration; INSERT-only role.
2. `record(action, subject, payload, actor)` helper computing prev_hash→hash.
3. Wire into the evaluation path first (S01-05).
4. Tests: chain links correctly; tampering with a row breaks verification;
   determinism (same content → same hash); no update/delete path.
5. **security-review** (tamper-evidence) + code-review; commit.

## Reference

ADR-0004; T00-03 temporal, T00-05 explainability (reproducibility contracts).
