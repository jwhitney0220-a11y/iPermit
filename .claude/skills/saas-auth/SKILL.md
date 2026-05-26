---
name: saas-auth
description: Use when implementing or modifying authentication, identity, password handling, JWT/session tokens, RBAC roles/permissions, or OAuth/SSO in iPermit.
---

# saas-auth — identity, tokens & RBAC

**Authority:** `docs/architecture/adr-0002-auth-rbac-tenant-isolation.md`.

## Conventions (ADR-0002)
- Resolve an `AuthenticatedIdentity` (subject, email, tenant memberships, roles, flags) from a bearer token per request — all auth flows funnel through this one abstraction.
- Roles: `consultant_user < regulatory_analyst < platform_admin`. Within analyst, capability flags `analyst:draft` / `analyst:review` / `analyst:publish` enforce SOP separation-of-duties at the workflow layer, not via extra roles.
- Day-one auth: self-managed email/password (or magic link), JWT bearer token.
- Enterprise SSO (OIDC/SAML) federates into the SAME `AuthenticatedIdentity` later — do NOT special-case it now; just don't block it.
- FastAPI deps: `get_current_identity` and `require_role(...)` / capability checks.

## Reference
open-saas `template/app/src/auth` (Wasp/Node — pattern for signup/login/OAuth flows only, not the stack).

## Guardrails
- **MANDATORY** run the **security-review** skill on every auth change.
- Hash passwords with bcrypt/argon2 (passlib). Never log tokens, passwords, or secrets. Sign/verify JWTs with a secret from env (`AUTH_*`, never committed).
- Functions ≤ 60 lines; tests cover login success/failure (RFC-9457 401) and role gating.
