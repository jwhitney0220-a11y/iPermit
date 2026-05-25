# packages/persistence

Shared persistence layer for iPermit (`ipermit_persistence`). Per
[ADR-0005](../../docs/architecture/adr-0005-persistence-data-layer.md):

- `Base` — the single SQLAlchemy 2.0 declarative base / `MetaData` (with a
  deterministic constraint-naming convention) that **all** ORM model packages
  inherit from, so Alembic and `create_all` see the whole schema.
- `make_engine` / `make_session_factory` / `database_url` — engine and session
  factories that resolve `DATABASE_URL` from the environment (T01-08), defaulting
  to local SQLite so tests and first-run dev need no PostgreSQL.

Domain models live in their own packages (e.g. `jurisdiction-models`) and import
`Base` from here. Migrations live at the repo root under `migrations/` (Alembic).
