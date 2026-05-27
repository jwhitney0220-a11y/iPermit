"""usage_record table

Revision ID: a1b2c3d4e5f6
Revises: 699a410cd559
Create Date: 2026-05-27 06:00:00.000000

Append-only usage event log for per-tenant metered-action tracking (S03-03).
One row per billable event; aggregates derived on read. Tenant-owned, so it
carries Postgres Row-Level Security keyed on ``app.current_tenant_id`` (ADR-0002),
exactly like the ``project``, ``evaluation``, and ``tenant_billing`` tables.
SQLite (tests/local) has no RLS; isolation relies on the app-layer tenant scope.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "699a410cd559"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_TABLE = "usage_record"


def _enable_rls() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(f"ALTER TABLE {_RLS_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_RLS_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {_RLS_TABLE}_tenant_isolation ON {_RLS_TABLE} "
        "USING (tenant_id = current_setting('app.current_tenant_id', true)) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true))"
    )


def _disable_rls() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        f"DROP POLICY IF EXISTS {_RLS_TABLE}_tenant_isolation ON {_RLS_TABLE}"
    )
    op.execute(f"ALTER TABLE {_RLS_TABLE} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.create_table(
        "usage_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column(
            "metric",
            sa.Enum("evaluation", name="usage_metric", native_enum=False),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_usage_record_tenant_id_tenant"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_record")),
    )
    op.create_index(
        op.f("ix_usage_record_tenant_id"), "usage_record", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_usage_record_occurred_at"),
        "usage_record",
        ["occurred_at"],
        unique=False,
    )
    _enable_rls()


def downgrade() -> None:
    _disable_rls()
    op.drop_index(op.f("ix_usage_record_occurred_at"), table_name="usage_record")
    op.drop_index(op.f("ix_usage_record_tenant_id"), table_name="usage_record")
    op.drop_table("usage_record")
