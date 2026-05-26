"""Database session wiring for the API (S01-03).

A thin layer over ``ipermit_persistence`` (ADR-0005): one engine/session factory
resolved from ``DATABASE_URL``, a FastAPI ``get_session`` dependency, and the
PostgreSQL Row-Level-Security hook. ``apply_tenant_scope`` sets the
``app.current_tenant_id`` GUC for the current transaction so the RLS policies
attached in migration 3c4eea27eb8b can see the active tenant (ADR-0002). On
SQLite (tests/local) it is a no-op and isolation relies on the application-layer
tenant filter — the two-layer model ADR-0002 specifies.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from ipermit_persistence import make_engine, make_session_factory
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from .settings import get_settings


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Build (once) the session factory bound to the configured database."""
    engine = make_engine(get_settings().database_url)
    return make_session_factory(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session and always close it."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def apply_tenant_scope(session: Session, tenant_id: str) -> None:
    """Pin the current transaction's tenant for Postgres RLS (no-op on SQLite)."""
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": tenant_id},
        )
