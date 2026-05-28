# Deploy & runtime (S07-05)

**Status:** Active (skeleton; concrete cloud provider TBD in T01-16)
**Owner ticket(s):** S07-05 (SAAS-07 deploy stack)
**Related:** [environments.md](./environments.md), [infrastructure/README.md](../../infrastructure/README.md), [postgis-planning.md](./postgis-planning.md), `services/api/Dockerfile`, `docker-compose.yml`

This is the deploy contract for the iPermit API. It's intentionally a *skeleton* — the topology and contracts are firm, the cloud provider is selected when T01-16 lands.

---

## 1. Image

`services/api/Dockerfile` is a multi-stage build off `python:3.11-slim-bookworm`. Build it from the repo root so the monorepo's packages and rule store are reachable:

```bash
docker build -f services/api/Dockerfile -t ipermit/api:dev .
```

The runtime stage:

- runs as a non-root `ipermit` user
- exposes port 8000 (`uvicorn ipermit_api.app:app`)
- carries every package the API imports (`services/{api,rules-engine,gis-engine}` + `packages/*` + `rules/` + `migrations/`)
- bakes `PYTHONPATH` so the monorepo source roots resolve without `pip install -e`

Workers are configured by the orchestrator (ECS task def, Cloud Run, k8s Deployment), not baked into the image, so the same image runs at any concurrency.

## 2. Local integration (docker-compose)

`docker-compose.yml` at the repo root brings up the API container against a real Postgres + PostGIS so a developer can exercise migrations, RLS, and the upload path without standing up cloud infrastructure:

```bash
docker compose up --build
```

The `api` service runs `alembic upgrade head` before starting `uvicorn`, so a fresh `compose up` is bootable.

The unit test suite still uses the in-process SQLite engine via the FastAPI `TestClient` fixtures — compose is the "does it actually run" smoke loop, not a replacement for the gates.

## 3. Liveness vs readiness

Per S07-03 the API exposes two probes:

| Path | Purpose | Effect on traffic |
| --- | --- | --- |
| `/healthz` | Liveness — the process is running | Restart-only on failure |
| `/readyz` | Readiness — DB session can `SELECT 1` | Drain from the load-balancer until green |

The terraform `service-hosting` module input `readiness_path` defaults to `/readyz` so the load-balancer health-check matches.

## 4. Configuration & secrets

`.env.example` is the authoritative inventory of every env var the API reads (T01-08). At deploy:

1. **Non-secret** values come from `infrastructure/terraform/environments/<env>/terraform.tfvars` and are injected via the orchestrator's `env` map (the module's `var.env`).
2. **Secrets** come from the cloud secret manager and are injected via `var.secret_refs` (`map(name -> secret_ref)`). The application never sees the raw secret in the repo or in tfvars.
3. **Hardening** (S07-01) — `API_CORS_ALLOWED_ORIGINS` and `API_TRUSTED_HOSTS` must enumerate the public hostnames outside `local`; `validate_security` raises at startup otherwise.

## 5. Terraform layout

```
infrastructure/terraform/
├── main.tf                       # root composition (wires modules)
├── variables.tf                  # environment inputs
├── modules/
│   ├── database/                 # PostgreSQL 16 + PostGIS (T01-09 / T01-16)
│   ├── storage/                  # uploads / deliverables bucket
│   └── service-hosting/          # API container — S07-05
└── environments/{staging,production}/
```

`modules/service-hosting` carries the input/output contract for the API container (image, port, desired count, env, secrets, readiness path). Concrete resources (ECS service / Cloud Run / k8s Deployment) get filled in once the hosting decision lands in T01-16.

## 6. Open follow-ups

- **CI/CD module** — build, push, deploy on green main (`infrastructure/terraform/modules/cicd`, declared but not yet scaffolded).
- **Concrete cloud provider** for `service-hosting` — decided in T01-16, applied here.
- **OpenTelemetry exporter** wiring (the `OTEL_EXPORTER_OTLP_ENDPOINT` env var exists; emission lives behind the S07-03 access-log middleware seam).
