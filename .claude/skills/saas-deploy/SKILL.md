---
name: saas-deploy
description: Use when working on infrastructure-as-code, managed Postgres/PostGIS provisioning, CI/CD deploy pipelines, or environment/secret configuration.
---

# saas-deploy — infra, env & deploy

**Authority:** `docs/architecture/adr-0001-tech-stack.md`, `docs/operations/environments.md`, `docs/operations/postgis-planning.md`.

## Conventions
- IaC in `infrastructure/terraform` — `database` + `storage` modules; the cloud provider is not yet chosen (variables are provider-neutral). Implement the module dirs when picking a provider.
- Database: managed PostgreSQL 16 + PostGIS (`postgis/postgis:16-3.4` for CI/devcontainer).
- Environments: `IPERMIT_ENV` ∈ `local`/`staging`/`production`. Secrets referenced via `*_SECRET_REF` — **never commit real secrets**. `DATABASE_URL` drives both the app engine and Alembic.
- CI: extend `.github/workflows/ci.yml` with `terraform validate` and a deploy job when ready. The devcontainer has Python 3.11 + Node 20 + PG client; add a `postgis` service container for spatial work.

## Guardrails
Migrations run via Alembic (`migrations/`), never implicit `create_all` in production. Pin tool versions to match pre-commit/CI. Functions ≤ 60 lines.
