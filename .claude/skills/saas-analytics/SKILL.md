---
name: saas-analytics
description: Use when adding usage metrics, operational dashboards, or regulatory rule-health monitoring.
---

# saas-analytics — usage & rule-health metrics

**Reference:** open-saas `template/app/src/analytics` (stats/operations pattern).

## Conventions
- Aggregate from the audit and evaluation tables — do not add a parallel write path.
- Track: per-tenant usage (evaluations, exports), and **rule health** — frequently overridden rules, uncertainty-heavy outputs, stale citations / broken source links (roadmap T08-03 / T08-05).
- Keep tenant-scoped analytics isolated (use **saas-multitenancy**); platform-wide rule-health is analyst-only.
- Surface results in the analyst/admin portal (**saas-admin-portal**).

## Guardrails
No PII or raw secrets in metrics. Deterministic aggregation (sorted, reproducible). Functions ≤ 60 lines.
