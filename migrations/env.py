"""Alembic migration environment (T02-01).

Resolves the database URL from the environment (T01-08) and binds Alembic to the
shared metadata so every iPermit ORM model is covered by autogenerate. Model
packages are imported for their side effect of registering tables on
``Base.metadata``.
"""

from __future__ import annotations

# Import model modules so their tables register on Base.metadata.
import ipermit_jurisdictions.models  # noqa: F401
from alembic import context
from ipermit_persistence import Base, database_url
from sqlalchemy import engine_from_config, pool

config = context.config
config.set_main_option("sqlalchemy.url", database_url())
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL without a live DB connection."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
