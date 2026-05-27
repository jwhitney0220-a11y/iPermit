"""ORM models for tenancy, projects, evaluations, and audit (SAAS-01 / S01-01).

These are the first *tenant-owned* tables in iPermit. They implement ADR-0002's
tenancy model (every project/evaluation row carries a non-null ``tenant_id``) and
ADR-0004's append-only, hash-chained audit log. They register on the shared
``ipermit_persistence.Base`` (ADR-0005) so Alembic and ``create_all`` see them
alongside the jurisdiction and regulatory models.

Regulatory data (rules, jurisdictions) is deliberately NOT modelled here — it is
platform-global, not tenant data (ADR-0002). Only project data is tenant-private.

Portable across SQLite (tests/local) and PostgreSQL (staging/prod): enums render
as ``VARCHAR + CHECK`` and JSON uses the portable ``JSON`` type. Row-Level
Security policies are attached to the tenant-owned tables by the Alembic
migration (Postgres only; a no-op on SQLite).
"""

from __future__ import annotations

import datetime

from ipermit_persistence import Base
from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

#: The three platform roles (ADR-0002), hierarchical.
PLATFORM_ROLES = ("consultant_user", "regulatory_analyst", "platform_admin")

#: Capability flags within the analyst tier (ADR-0002 separation-of-duties).
ANALYST_CAPABILITIES = ("analyst:draft", "analyst:review", "analyst:publish")

# native_enum=False renders as VARCHAR + CHECK — portable SQLite <-> PostgreSQL.
_role_enum = Enum(*PLATFORM_ROLES, name="platform_role", native_enum=False)

#: Tables that hold tenant-private data and therefore get RLS policies (ADR-0002).
TENANT_OWNED_TABLES = ("project", "evaluation")


def _utcnow() -> datetime.datetime:
    """Timezone-aware UTC now (audit ``occurred_at`` and row timestamps)."""
    return datetime.datetime.now(tz=datetime.UTC)


class Tenant(Base):
    """A billing/isolation boundary. One member (individual) or many (team)."""

    __tablename__ = "tenant"

    tenant_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_individual: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class User(Base):
    """A login identity. ``platform_role`` is the ADR-0002 role floor."""

    __tablename__ = "app_user"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    platform_role: Mapped[str] = mapped_column(
        _role_enum, default="consultant_user", nullable=False
    )
    # Capability flags within the analyst tier (ADR-0002): e.g. analyst:draft,
    # analyst:review, analyst:publish. A role grant is the capability floor;
    # these add the per-action grants the SOP separation-of-duties depends on.
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Membership(Base):
    """User<->tenant link. ``is_team_admin`` is a tenant-local capability."""

    __tablename__ = "membership"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("app_user.user_id"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenant.tenant_id"), nullable=False
    )
    is_team_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="memberships")
    tenant: Mapped[Tenant] = relationship(back_populates="memberships")


class Project(Base):
    """A consultant project. Tenant-owned (RLS-protected)."""

    __tablename__ = "project"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenant.tenant_id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("app_user.user_id"), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Evaluation(Base):
    """A persisted permit-matrix evaluation. Tenant-owned (RLS-protected).

    Stores the reproducibility triple (ADR-0003): ``inputs_hash``,
    ``ruleset_content_hash``, ``evaluation_date`` — plus the rendered matrix.
    """

    __tablename__ = "evaluation"

    evaluation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenant.tenant_id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project.project_id"), nullable=False, index=True
    )
    evaluation_date: Mapped[str] = mapped_column(String(10), nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    ruleset_content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    matrix: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("app_user.user_id"), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="evaluations")


class AuditRecord(Base):
    """Append-only, hash-chained audit record (ADR-0004).

    ``hash`` = sha256 over this record's canonical content plus the previous
    record's ``hash`` (``prev_hash``), forming a tamper-evident chain. Never
    updated or deleted; corrections are new compensating records.
    """

    __tablename__ = "audit_record"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    actor: Mapped[str] = mapped_column(String(320), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    hash: Mapped[str] = mapped_column(String(80), nullable=False)
