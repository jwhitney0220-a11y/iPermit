"""Engine and session factory (T02-01).

Reads the database URL from the environment (``DATABASE_URL``) per the T01-08
environment-configuration standard. Defaults to a local SQLite file so that
unit tests and first-run local development need no PostgreSQL. Production and
staging set ``DATABASE_URL`` to the managed PostgreSQL + PostGIS instance
(ADR-0001, T01-16).
"""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

_DEFAULT_URL = "sqlite+pysqlite:///./ipermit.db"


def database_url() -> str:
    """Resolve the database URL from the environment, with a local default."""
    return os.environ.get("DATABASE_URL", _DEFAULT_URL)


def make_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for the resolved (or given) URL."""
    return create_engine(url or database_url(), echo=echo, future=True)


def make_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Build a session factory bound to an engine (created if not supplied)."""
    return sessionmaker(bind=engine or make_engine(), expire_on_commit=False)
