"""jurisdiction_geometry table (PostGIS, S06-01)

Revision ID: e5b9a2c61a47
Revises: c7a2e9f4d18b
Create Date: 2026-05-29 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e5b9a2c61a47"
down_revision: str | None = "c7a2e9f4d18b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Production-only spatial table for the PostGISGeometryStore (S06-01). Holds
# one row per jurisdiction/overlay geometry — see jurisdiction-naming.md §9.
# SQLite (tests/local) has no PostGIS; the migration no-ops there so the
# DB-free CI path stays intact (ADR-0005 SQLite-for-tests pattern).

_EXTENSION = "CREATE EXTENSION IF NOT EXISTS postgis"
_TABLE = (
    "CREATE TABLE jurisdiction_geometry ("
    "  id varchar(64) PRIMARY KEY,"
    "  geom geometry(GEOMETRY, 4326) NOT NULL"
    ")"
)
_INDEX = (
    "CREATE INDEX jurisdiction_geometry_geom_gist "
    "ON jurisdiction_geometry USING GIST (geom)"
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(_EXTENSION)
    op.execute(_TABLE)
    op.execute(_INDEX)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS jurisdiction_geometry_geom_gist")
    op.execute("DROP TABLE IF EXISTS jurisdiction_geometry")
