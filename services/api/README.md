# services/api

The iPermit public API — a composing **BFF** over the deterministic rules engine,
GIS confirmation, persistence, and tenancy packages (SAAS-01; service boundary
recorded in [ADR-0006](../../docs/architecture/adr-0006-public-api-service.md)).
FastAPI + the ADR-0003 response envelope; OpenAPI is the published contract.

## Layout

| Module | Responsibility |
|--------|----------------|
| `settings.py` | Env config (`IPERMIT_*`, `DATABASE_URL`, `AUTH_*`). |
| `db.py` | Session dependency + Postgres RLS tenant-scope hook (ADR-0002). |
| `auth.py` | `AuthenticatedIdentity`, bcrypt hashing, JWT, role guards (ADR-0002). |
| `envelope.py` | `{data, meta, advisories, warnings}` + RFC-9457 problems (ADR-0003). |
| `matrix.py` | `build_permit_matrix(SimulationResult)` → permit-matrix payload (T07-01). |
| `evaluate.py` | intake + confirmed GIS → `simulate_project` → matrix → persist. |
| `audit.py` | Append-only, hash-chained audit writer (ADR-0004). |
| `routers/` | `/api/v1/auth`, `/api/v1/projects`. |
| `app.py` | Application factory (`create_app`). |

## Run locally

```bash
pip install -r services/api/requirements.txt
alembic upgrade head                      # create tenancy tables
uvicorn ipermit_api.app:app --reload      # http://127.0.0.1:8000/docs
```

The deterministic libraries are imported from the monorepo source tree (the same
`sys.path` roots `tests/conftest.py` sets up); they are not redistributed here.
