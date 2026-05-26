# packages/tenancy-models

Tenant-owned ORM models — `Tenant`, `User`, `Membership`, `Project`,
`Evaluation` — plus the append-only `AuditRecord`. Implements ADR-0002 tenancy
(`tenant_id` + Postgres RLS) and ADR-0004 hash-chained audit on the shared
`ipermit_persistence.Base` (ADR-0005). Regulatory data stays platform-global and
is not modelled here. Consumed by the `services/api` public surface (SAAS-01).
