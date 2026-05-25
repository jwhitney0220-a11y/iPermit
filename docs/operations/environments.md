# Environment Configuration Standard

**Status:** Active
**Owner ticket(s):** T01-08 (environment configuration system)
**Related:** [ADR-0001](../architecture/adr-0001-tech-stack.md), [`/.env.example`](../../.env.example), [`infrastructure/README.md`](../../infrastructure/README.md), [postgis-planning.md](./postgis-planning.md) (T01-16)

---

## 1. Purpose

This document defines how iPermit handles configuration and secrets across the
three runtime environments. It is the standard that [`/.env.example`](../../.env.example)
and the Infrastructure-as-Code (T01-09) implement against. The goals, in the
AGENTS.md priority order (Maintainability → Explainability → Traceability → ...):

- **One contract.** Every variable the platform reads is listed, with a comment,
  in `.env.example`. There is no second, undocumented source of configuration.
- **No secrets in git, ever.** Real credentials live in environment variables
  (local) or a secret manager (staging/production), never in a committed file.
- **Predictable naming** so an engineer can guess a variable name and find where
  it is read.

---

## 2. The three environments

| Environment   | `IPERMIT_ENV` | Purpose | Config source | Secrets source |
|---------------|---------------|---------|---------------|----------------|
| **Local**     | `local`       | Developer machines and the dev container (T01-12). | `.env` file (git-ignored), copied from `.env.example`. | Throwaway values inline in `.env`. Never real production secrets. |
| **Staging**   | `staging`     | Pre-production verification; mirrors production topology at lower scale. Spatial-extension and migration testing target (see T01-16). | Non-secret values from the IaC environment definition ([`infrastructure/terraform/environments/staging`](../../infrastructure/terraform/environments/staging)). | Secret manager. |
| **Production**| `production`  | Live consultant-facing platform. | Non-secret values from IaC ([`.../environments/production`](../../infrastructure/terraform/environments/production)). | Secret manager. |

The single switch `IPERMIT_ENV` selects behavior. Code MUST NOT branch on
hostnames, ad-hoc flags, or "is this prod?" heuristics — read `IPERMIT_ENV`.

### Environment parity

Staging exists to catch what local cannot: real managed Postgres + PostGIS,
real object storage, real secret-manager wiring. Keep staging and production
**structurally identical** (same IaC modules, same extensions, same migration
path) and let them differ only in scale and data. This parity is the
precondition for the spatial-extension testing called for in T01-16.

---

## 3. Secrets-handling policy

This is the non-negotiable part of the standard.

1. **Never commit a secret.** No passwords, API keys, tokens, signing secrets,
   or connection strings containing credentials in any tracked file. `.env.example`
   carries placeholders only.
2. **Local secrets** are throwaway values a developer puts in their own `.env`.
   They grant access to local-only resources. A leaked local secret must never
   grant access to staging or production.
3. **Staging/production secrets** are stored in a secret manager (the concrete
   product is selected with the hosting decision in T01-16 / T05-01 — e.g. the
   cloud provider's native secret manager). The application resolves them at
   startup or via the platform's secret-injection mechanism.
4. **`*_SECRET_REF` variables name the lookup, not the value.** A variable like
   `DATABASE_URL_SECRET_REF=ipermit/<env>/database-url` tells the app *where* to
   find the secret. The secret's value is never in the repo. This indirection is
   what lets the same image run in staging and production by changing only the
   `<env>` segment.
5. **No secret crosses an environment boundary.** Production secrets are not
   used in staging, and neither is ever copied to a laptop.
6. **Rotation** is an IaC + secret-manager operation (T01-09 / later), not a
   code change. Because the app reads a reference rather than a baked-in value,
   rotating a secret requires no redeploy of application code.

### `.env` must be git-ignored

Because `.env` holds local secrets, it MUST be ignored by git. Add the following
to the root `.gitignore` if it is not already present (this standard requires it;
the entry was not added by T01-08 to avoid editing files outside the ticket's
ownership — track it as a one-line follow-up):

```gitignore
# Local environment files — never commit (T01-08 standard)
.env
.env.*
!.env.example
```

A pre-commit secret-scan hook (T01-12) should additionally block accidental
commits of credential-shaped strings.

---

## 4. Naming conventions

- **Case:** `UPPER_SNAKE_CASE`.
- **Component prefix** so the variable's owner is obvious at a glance:

  | Prefix       | Owns | Owning area |
  |--------------|------|-------------|
  | `IPERMIT_`   | Cross-cutting runtime (env name, log level, API bind). | platform |
  | `DB_`        | Database tuning (pool sizes, timeouts). | T01-09 / T02-01 |
  | `DATABASE_URL` / `DATABASE_URL_SECRET_REF` | Postgres connection (kept as the conventional name SQLAlchemy/tools expect). | T01-09 |
  | `GIS_`       | PostGIS + spatial upload settings. | T01-16 / EPIC-05 |
  | `STORAGE_`   | Object storage for uploads/exports. | T01-09 / EPIC-05/07 |
  | `AUTH_`      | Auth/RBAC/session. | T01-14 |
  | `AI_`        | Constrained AI assistance. | EPIC-09 |

- **Secret references** end in `_SECRET_REF` and resolve to a secret-manager key.
- **Feature flags** are `<AREA>_FEATURES_ENABLED` or `<AREA>_<FEATURE>_ENABLED`,
  default `false`, so unfinished epics ship dark.
- **Booleans** are the lowercase strings `true` / `false`.

---

## 5. The `.env.example` contract

[`/.env.example`](../../.env.example) is the canonical inventory of configuration.
Engineering rules:

1. **Add on read.** The moment code starts reading a new variable, add it to
   `.env.example` in the same change, with a one-line comment explaining it.
2. **Placeholders only.** Use `CHANGE_ME_LOCAL_ONLY` for local-fillable secrets
   and a `ipermit/<env>/...` reference for managed secrets. No real values.
3. **Keep it grouped** by the component prefixes above, matching this document.
4. **Document defaults.** If the app has a safe built-in default, the example
   shows it; if a value is required with no default, the comment says so.
5. **No drift.** A value present in `.env.example` but unread by any code, or
   read by code but missing here, is a bug. T01-12 may add a check that fails CI
   on drift.

### How config is loaded (target shape, implemented in T01-09 / T02-01)

Each FastAPI service loads configuration through a single typed settings object
(Pydantic `BaseSettings`) that reads from the process environment. Precedence,
highest first:

1. Real process environment variables (set by the secret manager / IaC in
   staging/production, or by the shell in CI).
2. The `.env` file (local development only).
3. The typed default declared on the settings model.

Services validate required settings at startup and fail fast with a clear error
naming the missing variable — never start half-configured.

---

## 6. Quick start (local)

```bash
cp .env.example .env
# edit .env: set local-only DB password, leave *_SECRET_REF lines as-is
# (they are unused locally), keep AI_FEATURES_ENABLED=false.
```

Staging and production never use a `.env` file; their configuration comes from
IaC and the secret manager described above.
