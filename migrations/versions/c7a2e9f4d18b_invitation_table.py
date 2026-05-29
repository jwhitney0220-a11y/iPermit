"""invitation table

Revision ID: c7a2e9f4d18b
Revises: b4786b301ca7
Create Date: 2026-05-28 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7a2e9f4d18b"
down_revision: str | None = "b4786b301ca7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``invitation`` table for the team-invite + verify flow (S07-02)."""
    op.create_table(
        "invitation",
        sa.Column("invitation_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by", sa.String(length=36), nullable=False),
        sa.Column("is_team_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant_id"],
            name=op.f("fk_invitation_tenant_id_tenant"),
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["app_user.user_id"],
            name=op.f("fk_invitation_invited_by_app_user"),
        ),
        sa.PrimaryKeyConstraint("invitation_id", name=op.f("pk_invitation")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invitation_token_hash")),
    )
    op.create_index(op.f("ix_invitation_tenant_id"), "invitation", ["tenant_id"])
    op.create_index(op.f("ix_invitation_email"), "invitation", ["email"])


def downgrade() -> None:
    """Drop the invitation table."""
    op.drop_index(op.f("ix_invitation_email"), table_name="invitation")
    op.drop_index(op.f("ix_invitation_tenant_id"), table_name="invitation")
    op.drop_table("invitation")
