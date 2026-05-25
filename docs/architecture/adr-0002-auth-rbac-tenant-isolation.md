# ADR-0002: Authentication, RBAC & Tenant Isolation

- **Status:** Proposed (merging this PR constitutes sign-off)
- **Date:** 2026-05-25
- **Deciders:** Product owner, engineering, regulatory operations lead
- **Supersedes:** none
- **Related:** [`/AGENTS.md`](../../AGENTS.md) (*Human Review Workflow*, *Regulatory Analyst SOP Requirements*, *Data Governance*, *User Feedback Queue*), [`ADR-0001`](./adr-0001-tech-stack.md), roadmap T01-14 (this ticket), T01-13 (CODEOWNERS/templates), T00-09 (analyst SOP), T08-02 (analyst shell), T08-04 (publication workflow), T08-06 (feedback queue), T06-02 (intake), T01-04 (audit log), T01-15 (API contract)

> ADRs are immutable once accepted. To change a decision, write a new ADR that
> supersedes this one rather than editing this file.

---

## Context

EPIC-01 produces the first real services. Before the consultant app (T06-01),
the analyst portal (T08-02), and the publication workflow (T08-04) can exist, the
platform needs a single, coherent answer to three questions: *who are you*
(authentication), *what may you do* (authorization / RBAC), and *whose data may
you touch* (tenant isolation).

These are not independent. The analyst SOP (T00-09) already assumes RBAC: it
requires that "the drafting analyst and reviewing analyst on the same rule MUST
be different people," that publication authority is "an RBAC role granted under
T01-14," and that audit can confirm "the publication move was performed by a
publishing analyst (RBAC)." The publication workflow (T08-04) and analyst portal
(T08-02) are explicitly role-gated against this ticket. So RBAC here is a
*foundation other tickets depend on*, not a standalone feature.

Constraints inherited from AGENTS.md and ADR-0001:

- The product serves **two account shapes**: individual consultants and
  enterprise teams. Project data must be **isolated between tenants**.
- The platform must support **future SSO/OAuth** without re-architecting.
- Backend is **Python/FastAPI + PostgreSQL** (ADR-0001). Whatever we choose must
  fit a server-side authority model where clients are thin.
- **Maintainability and traceability** rank above feature breadth. The auth model
  must be auditable: every privileged action (rule publication, feedback
  disposition) is attributable to a real identity that the audit log (T01-04) can
  record.

What this ADR decides: the **role model, the tenancy model, the isolation
mechanism, and the SSO path**. What it explicitly defers: the concrete auth
provider/library, the session/token format details, and password/MFA policy.
Those are reversible implementation choices; the role and tenancy *model* is the
expensive-to-change decision and is fixed here.

---

## Decision

### Role model — three platform roles, hierarchical

iPermit recognizes exactly three platform roles, matching AGENTS.md and the T00-09
analyst SOP. Higher roles are supersets of the capabilities of lower roles.

| Role | Capabilities (summary) |
|------|------------------------|
| `consultant_user` | Create/evaluate projects, view permit matrices and explanations, export deliverables, submit feedback (T08-06). Scoped to their own tenant. |
| `regulatory_analyst` | Everything a consultant can do on internal projects, **plus** draft/review rules, run benchmarks, triage the feedback queue. Access to the analyst portal (T08-02). Platform-internal, not tenant-scoped to a customer. |
| `platform_admin` | Everything an analyst can do, **plus** publication authority (T08-04), user/tenant administration, role grants, and audit-log read access. |

The hierarchy is `platform_admin > regulatory_analyst > consultant_user`. A role
grant is the *floor* of capability, not the ceiling: a `platform_admin` can do
anything a `regulatory_analyst` can.

**Separation-of-duties refinement.** The single hierarchy is not sufficient for
the SOP's "drafter ≠ reviewer" and "publisher ≠ drafter" rules (T00-09 §1).
Those are per-rule, per-action constraints, not standing roles. We model them as
**capability flags within the analyst tier** rather than new roles:

- `analyst:draft` — may create/edit draft rules.
- `analyst:review` — may sign off peer review.
- `analyst:publish` — publication authority (the "publishing analyst" of T00-09 §1.3).

A human may hold several flags. The *per-rule* constraint (you cannot review your
own draft) is enforced at the workflow layer (T08-04) by comparing the acting
identity against the rule's recorded drafter — RBAC grants the *capability*; the
workflow enforces the *separation*. This keeps the role table small while
satisfying the SOP. `analyst:publish` corresponds to the SOP "publishing analyst"
and is normally held only by `platform_admin` plus a small set of senior analysts.

### Role-to-team mapping (CODEOWNERS, T01-13)

The same role taxonomy maps onto the GitHub CODEOWNERS team handles created in
T01-13, so that *repository* authority and *platform* authority stay consistent:

| Platform role / flag | Suggested CODEOWNERS team |
|----------------------|---------------------------|
| `analyst:draft` / `analyst:review` | `@ipermit/regulatory-analysts` |
| `analyst:publish` | `@ipermit/publishing-analysts` |
| `platform_admin` | `@ipermit/platform-admins` |

Rule files under `rules/` are owned by the analyst teams; service code is owned by
engineering. T01-13 owns the actual CODEOWNERS file; this ADR fixes the *mapping*
so that "who can approve a rule PR" and "who can publish in the running platform"
are the same people by construction.

### Tenancy model — `tenant_id` scoping with PostgreSQL Row-Level Security

Every tenant-owned row (projects, intake records, evaluations, exports, feedback
items) carries a non-null `tenant_id` foreign key to a `tenants` table.

- An **individual consultant account** is a tenant with one member.
- An **enterprise team account** is a tenant with many members and an internal
  `team_admin` membership flag (a tenant-local capability, *not* a platform role).
  Enterprise membership/seat management is intra-tenant and does not grant any
  platform role.

Isolation is enforced at **two layers**, defense in depth:

1. **Application layer (FastAPI).** Every authenticated request resolves to an
   identity and its tenant(s). Repository/query helpers require an explicit
   tenant scope; there is no "fetch by id without tenant" path for tenant-owned
   tables.
2. **Database layer (PostgreSQL Row-Level Security).** Tenant-owned tables have
   RLS policies keyed on a session variable (e.g. `app.current_tenant_id`) set
   per connection/transaction by the service. Even an application bug that omits
   the tenant filter cannot leak cross-tenant rows, because the database refuses
   to return them.

RLS is chosen over physical separation (database-per-tenant, schema-per-tenant)
because it scales to many small individual-consultant tenants without operational
explosion, keeps a single migration surface (consistent with ADR-0001's
single-engine PostgreSQL decision), and aligns with the *Maintainability* priority.
Physical isolation remains available later for a specific high-sensitivity
enterprise tenant if one ever requires it — the `tenant_id` model is the
prerequisite for either path.

**What is *not* tenant-scoped.** Regulatory data — rules, jurisdiction records,
benchmarks, the rule content store — is **platform-global**, not tenant data. All
tenants evaluate against the same canonical ruleset. Analysts operate on this
global regulatory layer and are therefore not bound by customer-tenant RLS;
analyst/admin access is governed by role, not by `tenant_id`. This separation is
deliberate: the regulatory intelligence database is the primary moat (AGENTS.md
*Core Competitive Moats*) and is shared, while *project* data is private.

### Gating the analyst and publication surfaces

- **T08-02 (analyst portal shell)** requires `regulatory_analyst` or higher. The
  shell is a separate frontend from the consultant app (per its roadmap entry);
  the API enforces the role on every analyst endpoint regardless of which client
  calls it (clients are thin per ADR-0001).
- **T08-04 (publication workflow)** requires the `analyst:publish` capability and,
  additionally, the workflow-layer separation-of-duties check (publisher ≠
  drafter). Every transition the publication workflow performs is written to the
  audit log (T01-04) with the acting identity.
- **T08-06 (feedback queue)** dispositions (confirm/reject) require
  `regulatory_analyst`. Consultants may *submit* feedback (their own tenant) but
  may never disposition it, satisfying the AGENTS.md *User Feedback Queue* rule
  that feedback "MUST NOT auto-publish" or "bypass analyst verification."

### Authentication & SSO path — interface now, provider later

We commit to an **identity abstraction**, not a provider. The services depend on
an `AuthenticatedIdentity` (subject id, email, tenant memberships, roles, capability
flags) resolved from a bearer token on each request. The token verifier is a
single, swappable component.

This makes the SSO/OAuth path a *configuration*, not a rewrite:

- **Day one:** email/password (or magic-link) for individual consultants and
  enterprise members.
- **Enterprise SSO (future):** OIDC / SAML federation where the identity provider
  (the customer's Okta/Azure AD/Google Workspace) asserts identity and the
  iPermit tenant maps the federated user to a tenant membership and platform role.
  Because identity resolution already flows through the abstraction, adding an
  OIDC verifier is additive.

Role and tenant membership are **always iPermit-owned**, even under SSO: the
external IdP asserts *who you are*; iPermit decides *what you may do here* and
*which tenant you belong to*. This keeps the audit trail authoritative.

### Auth provider/library — deferred, options presented for sign-off

The concrete provider is **deferred** (it is reversible behind the abstraction
above). For the sign-off conversation, three viable directions:

| Option | Pros | Cons | Fit |
|--------|------|------|-----|
| **Self-managed** (FastAPI + a vetted library for password hashing + JWT/session, e.g. `authlib`/`fastapi-users`) | Full control; no per-MAU cost; data stays in our DB; simplest tenant/role modeling since it's all our schema | We own MFA, password reset, breach monitoring, SSO connector maintenance, security patching | Strong for MVP volume; aligns with "AI is not the moat, regulatory data is" — auth is undifferentiated, but cost and control matter early |
| **Auth0 / Okta** | Mature SSO/SAML/OIDC out of the box; offloads MFA, password reset, breach detection | Per-MAU cost grows with consultants; another vendor in the data path; enterprise SSO connectors are the paid tier | Strong if enterprise SSO arrives early and we want to not build it |
| **AWS Cognito** | Cheap at low volume; native if we host on AWS (ties to T01-09 IaC); OIDC/SAML support | Developer ergonomics are rough; tenant/role modeling is awkward; lock-in | Reasonable if IaC (T01-09) lands on AWS |
| **Clerk** | Excellent DX, fast to ship, good React components for T06-01 | Newer vendor; per-MAU cost; less battle-tested for SAML-heavy enterprise | Good for speed-to-MVP on the consultant app |

**Recommendation for sign-off:** start **self-managed** behind the identity
abstraction for the MVP (low volume, full control of the role/tenant schema, no
per-seat cost, no third party in the regulatory-data path), and **plan to adopt a
managed OIDC provider for enterprise SSO** when the first enterprise customer
requires federation. The abstraction makes that a swap of one component, not a
migration. If T01-09 commits to AWS, re-evaluate Cognito for the federation layer
specifically. This is the decision we ask the deciders to confirm.

---

## Consequences

### Positive

- The SOP's separation-of-duties (T00-09) is enforceable by construction:
  capabilities in RBAC, per-rule separation in the workflow layer (T08-04).
- Two-layer tenant isolation (app + Postgres RLS) means an application bug cannot
  leak cross-tenant project data — a direct service of the *Traceability* and
  data-governance priorities.
- Regulatory data stays global and shared, protecting the moat while keeping
  customer project data private.
- The identity abstraction turns "add enterprise SSO" into additive work.
- Role↔CODEOWNERS mapping keeps repo authority and platform authority consistent.

### Negative / costs

- RLS adds discipline: every connection must set the tenant session variable, and
  migrations must remember to attach policies to new tenant-owned tables. A CI
  check (T01-07) should assert every tenant-owned table has an RLS policy.
- Self-managed auth means we own MFA, reset flows, and security patching until/if
  we adopt a provider. Accepted for MVP; revisited at enterprise SSO.
- The capability-flag model (vs. flat roles) is slightly more to reason about, but
  the alternative (a role per separation rule) is worse.

### Neutral / deferred

- Token format (JWT vs. opaque session), session lifetime, refresh strategy → impl.
- MFA policy, password rules → impl / security review.
- Concrete auth provider → deferred above; recommendation pending sign-off.
- Enterprise seat/billing model → product, not this ADR.

---

## Alternatives Considered

### Flat roles with no capability flags

Model `analyst:draft`/`review`/`publish` as distinct top-level roles instead of
flags within the analyst tier. **Rejected** because it multiplies the role table,
breaks the clean hierarchy, and still cannot express the *per-rule* "not your own
draft" constraint (which is inherently workflow-state, not a standing grant). Flags
plus a workflow check is simpler and correct.

### Schema-per-tenant or database-per-tenant isolation

Physically separate each tenant's data. **Rejected** as the default: it does not
scale to many individual-consultant tenants without heavy operational overhead and
conflicts with ADR-0001's single-engine simplicity. RLS gives strong isolation at
one migration surface. Physical isolation is kept as a future option for a single
high-sensitivity enterprise tenant; the `tenant_id` model is the prerequisite for
moving one tenant out if ever needed.

### Adopt a managed provider (Auth0/Cognito/Clerk) on day one

Offload all of auth immediately. **Rejected as the default** for MVP because it
adds per-seat cost and a third party in the data path for an undifferentiated
capability, and because our tenant/role model is bespoke enough that we'd be
fighting the provider's model early. We keep it as the recommended path *for the
enterprise-SSO layer specifically*, behind the abstraction.

### Tenant-scoping regulatory rules too

Make rules tenant-private. **Rejected** outright: it contradicts the moat (a
single shared regulatory intelligence database) and would make benchmark replay
and audit reproducibility (T00-03, T01-04) incoherent. Rules are global; only
project data is tenant-private.

---

## Open Questions (do not block this ADR)

- Final auth provider for MVP and for enterprise SSO — recommendation above, awaiting
  deciders; revisit against T01-09 (IaC platform choice).
- Whether enterprise tenants may self-manage their own member↔role mapping under
  SSO, or whether iPermit ops retains role grants — leans toward iPermit-owned.
- Token format and session lifetime — implementation detail for the first auth PR.
- Service-to-service auth between the rules-engine, gis-engine, and API gateway
  (internal trust boundary) — to be specified alongside T01-15 / deployment.
