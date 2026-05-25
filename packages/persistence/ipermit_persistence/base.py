"""Shared SQLAlchemy declarative base and naming conventions (T02-01).

Every iPermit ORM model across packages inherits from ``Base`` here so they all
register on a single ``MetaData`` — Alembic autogenerate and ``create_all`` see
the whole schema. The naming convention makes constraint/index names
deterministic, which keeps migrations stable and reviewable.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint naming so Alembic emits stable, reviewable names.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by all iPermit ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
