"""audit append-only trigger

Revision ID: d4607521958a
Revises: 04a85d8df1a1
Create Date: 2026-05-27 04:10:15.479688
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'd4607521958a'
down_revision: str | None = '04a85d8df1a1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enforce ADR-0004's append-only audit log at the database layer: a Postgres
# trigger blocks UPDATE/DELETE on audit_record even for the application role, so
# the hash chain cannot be silently rewritten. SQLite (tests/local) has no such
# trigger; tamper-evidence there relies on the hash chain alone.

_FN = (
    "CREATE OR REPLACE FUNCTION ipermit_audit_append_only() RETURNS trigger "
    "AS $$ BEGIN RAISE EXCEPTION 'audit_record is append-only (ADR-0004)'; END; $$ "
    "LANGUAGE plpgsql"
)
_TRIGGER = (
    "CREATE TRIGGER audit_record_append_only "
    "BEFORE UPDATE OR DELETE ON audit_record "
    "FOR EACH ROW EXECUTE FUNCTION ipermit_audit_append_only()"
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(_FN)
    op.execute(_TRIGGER)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS audit_record_append_only ON audit_record")
    op.execute("DROP FUNCTION IF EXISTS ipermit_audit_append_only()")
