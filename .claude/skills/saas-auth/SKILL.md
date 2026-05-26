---
name: saas-auth
description: >
  Build iPermit authentication and authorization — password hashing, JWT,
  AuthenticatedIdentity, RBAC roles, and (later) OAuth/SSO. Use for auth tickets
  (S01-02, S02-01, S07-04). Grounded in ADR-0002; open-saas src/auth is the
  feature pattern.
---

# saas-auth — authentication & RBAC

ADR-0002 (`docs/architecture/adr-0002-auth-rbac-tenant-isolation.md`) is
authoritative. Stack: FastAPI + Postgres. open-saas `auth/` (in
`.claude/references/open-saas/auth`) is a Wasp/Node pattern reference — translate
intent.

## Conventions

- **Password hashing**: Argon2id (or bcrypt) via `passlib`/`argon2-cffi`. Never
  store or log plaintext. Constant-time verify.
- **Sessions**: short-lived JWT access token + refresh token. Sign with a secret
  from env (T01-08 config); never hardcode. Include `sub` (user id), `tenant_id`,
  and `role`.
- **`AuthenticatedIdentity`**: a typed object (user_id, tenant_id, role,
  capabilities) resolved by a FastAPI dependency from the token. Routes depend on
  it; it feeds tenant scoping (saas-multitenancy) and RBAC.
- **Role hierarchy** (ADR-0002): `platform_admin` > `regulatory_analyst` >
  `consultant_user`. S01-02 ships the minimal set; S02-01 adds full RBAC +
  capability flags. Authorization checks are explicit and centralized (a
  `require(role|capability)` dependency), never ad hoc.
- **OAuth/SSO (OIDC/SAML)**: deferred to S07-04; design the identity model so SSO
  slots in without schema churn.

## Build checklist

1. User + credential models (tenant-scoped); Alembic migration.
2. Hashing + token issue/verify utilities; `AuthenticatedIdentity` dependency.
3. Endpoints: signup, login, refresh, me (via saas-api envelope + RFC-9457).
4. RBAC dependency; deny-by-default on protected routes.
5. Tests: hashing round-trip, token expiry/tamper rejection, role gating,
   wrong-tenant rejection.
6. **security-review mandatory**; then code-review, run/verify, commit.

## Reference

ADR-0002; `.claude/references/open-saas/auth` (pattern only).
