---
name: saas-admin-portal
description: Use when building internal analyst/admin dashboards or role-gated internal navigation (apps/analyst-portal) — rule review, publication, QA/QC, tenant/user admin.
---

# saas-admin-portal — internal analyst/admin app

**Reference:** open-saas `template/app/src/admin` (admin dashboard pattern).

## Conventions
- Separate app from the consultant frontend: `apps/analyst-portal` (roadmap T08-02). Use the **saas-frontend** skill for the SPA mechanics.
- Role-gated via RBAC (`regulatory_analyst` / `platform_admin`) — see **saas-auth**.
- Surfaces: rule review + publication workflow (T08-04), QA/QC dashboard (render `scripts/qa/qa_report.py` output — T04-05), rule-health monitoring (T08-05), tenant/user administration.
- Read-mostly. Mutating actions (publish a rule, grant a role) MUST go through the publication/approval workflow and write an audit record (**saas-audit**).

## Guardrails
Reuse the same OpenAPI-generated client + `packages/shared-schemas/typescript` types. Never expose tenant data across tenants. Functions ≤ 60 lines.
