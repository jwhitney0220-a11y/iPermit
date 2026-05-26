"""Multi-tenant ORM models for the SaaS spine (S01-01).

Implements the tenancy + project persistence layer mandated by ADR-0002
(`docs/architecture/adr-0002-auth-rbac-tenant-isolation.md`). Every tenant-owned
table carries a non-null ``tenant_id`` FK to ``tenant``; cross-tenant isolation
is enforced in the application layer by ``ipermit_tenancy.session`` and, on
PostgreSQL, by Row-Level Security policies attached in the Alembic migration.

Portability follows ADR-0005: enums use ``Enum(native_enum=False)`` (VARCHAR +
CHECK) and structured columns use the portable ``JSON`` type, so the identical
schema builds on SQLite (tests/CI) and PostgreSQL (staging/production).

User identity is deliberately NOT modelled here. ``user_id`` columns are opaque
strings; the ``User`` model and the real foreign keys arrive in S01-02. The
unique constraint on ``(tenant_id, user_id)`` and the role enum are defined now
so the membership table is correct ahead of that ticket.
"""

from __future__ import annotations

import datetime

from ipermit_persistence import Base
from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

#: A tenant is either a single individual consultant or an enterprise team
#: (ADR-0002 "two account shapes").
TENANT_KINDS = ("individual", "enterprise")

#: The three platform roles from ADR-0002. Held per (tenant, user) membership.
MEMBERSHIP_ROLES = ("platform_admin", "regulatory_analyst", "consultant_user")

# native_enum=False + create_constraint renders VARCHAR + CHECK — portable
# SQLite <-> PostgreSQL, and the CHECK is enforced on both (off-list values are
# rejected at write time, not silently stored).
_tenant_kind_enum = Enum(
    *TENANT_KINDS, name="tenant_kind", native_enum=False, create_constraint=True
)
_membership_role_enum = Enum(
    *MEMBERSHIP_ROLES,
    name="membership_role",
    native_enum=False,
    create_constraint=True,
)


def _utcnow() -> datetime.datetime:
    """Timezone-aware UTC now (deterministic default factory for timestamps)."""
    return datetime.datetime.now(datetime.UTC)


class Tenant(Base):
    """A tenant — the isolation boundary for all customer project data."""

    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(_tenant_kind_enum, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    memberships: Mapped[list[TenantMembership]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        order_by="TenantMembership.id",
    )
    projects: Mapped[list[Project]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        order_by="Project.id",
    )


class TenantMembership(Base):
    """A user's membership of a tenant and the platform role they hold there.

    ``user_id`` is an opaque identifier (string/UUID). The ``User`` model and a
    real FK land in S01-02; until then no FK is declared so this table does not
    depend on a table that does not yet exist.
    """

    __tablename__ = "tenant_membership"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_membership_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(_membership_role_enum, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    tenant: Mapped[Tenant] = relationship(back_populates="memberships")


class Project(Base):
    """A tenant-owned project. The unit of work a consultant evaluates."""

    __tablename__ = "project"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Opaque user id (string/UUID); real User FK arrives in S01-02.
    created_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="projects")
    evaluations: Mapped[list[ProjectEvaluation]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectEvaluation.id",
    )


class ProjectEvaluation(Base):
    """A stored evaluation run for a project (the output of S01-04's engine).

    ``ruleset_version`` and ``result_summary`` are kept as portable JSON blobs;
    the evaluation contract is tied to ``ipermit_engine.simulate_project`` in
    S01-04. ``tenant_id`` is denormalised onto this table (not only reachable via
    ``project``) so the tenant-aware data path and Postgres RLS can filter it
    directly without a join.
    """

    __tablename__ = "project_evaluation"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id"), nullable=False, index=True
    )
    ruleset_version: Mapped[dict] = mapped_column(JSON, nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    result_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    evaluated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="evaluations")


#: Tables that carry a tenant_id and must be scoped/RLS-protected. Consumed by
#: ``ipermit_tenancy.session`` (app-layer filter) and the Alembic migration
#: (Postgres RLS policies). Keep this list authoritative — adding a tenant-owned
#: model means adding it here.
TENANT_OWNED_MODELS = (Project, ProjectEvaluation)
