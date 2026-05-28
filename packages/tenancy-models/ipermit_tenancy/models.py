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

#: Consultant-feedback lifecycle (T08-06). Disposition is analyst-only.
FEEDBACK_STATUSES = ("open", "confirmed", "rejected")
_feedback_status_enum = Enum(
    *FEEDBACK_STATUSES, name="feedback_status", native_enum=False
)

#: Billing plans (S03-01). ``free`` is the default entitlement before any paid
#: subscription; the paid tiers map to server-side Stripe Price IDs in settings.
BILLING_PLANS = ("free", "starter", "pro")
_billing_plan_enum = Enum(*BILLING_PLANS, name="billing_plan", native_enum=False)

#: Subscription status, mirroring the Stripe subscription lifecycle (S03-01).
#: ``none`` is the pre-subscription state; the rest track the Stripe status.
BILLING_STATUSES = ("none", "active", "past_due", "canceled", "incomplete")
_billing_status_enum = Enum(*BILLING_STATUSES, name="billing_status", native_enum=False)

# native_enum=False renders as VARCHAR + CHECK — portable SQLite <-> PostgreSQL.
_role_enum = Enum(*PLATFORM_ROLES, name="platform_role", native_enum=False)

#: Metered action types (S03-03). ``evaluation`` is the primary billable action;
#: the enum is append-only — new metrics are additive and never rename old values.
#: ``export`` (S03-04) meters deliverable exports. New values fit the existing
#: VARCHAR(10) column and are validated at the ORM layer, so no migration is
#: needed as long as the value length stays <= the longest original ("evaluation").
USAGE_METRICS = ("evaluation", "export")
_usage_metric_enum = Enum(*USAGE_METRICS, name="usage_metric", native_enum=False)

#: Rule-publication workflow states (S05-02 / T08-04). A proposal is created in
#: ``proposed`` and ends in ``approved`` (the promotion is in force), ``rejected``,
#: or ``rolled_back`` (an approved promotion reversed).
PUBLICATION_STATUSES = ("proposed", "approved", "rejected", "rolled_back")
_publication_status_enum = Enum(
    *PUBLICATION_STATUSES, name="publication_status", native_enum=False
)

#: Target rule statuses a publication can promote to (matches the rule-object
#: schema's lifecycle: draft is the source, archived/effective are the targets).
PUBLICATION_TARGETS = ("effective", "archived")
_publication_target_enum = Enum(
    *PUBLICATION_TARGETS, name="publication_target", native_enum=False
)

#: Tables that hold tenant-private data and therefore get RLS policies (ADR-0002).
TENANT_OWNED_TABLES = ("project", "evaluation", "tenant_billing", "usage_record")


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


class Feedback(Base):
    """Consultant feedback on an evaluation, triaged by analysts (T08-06).

    Tenant-owned: a consultant submits and sees only their own tenant's feedback
    (RLS + app-layer scope). Disposition (confirm/reject) is analyst-only and
    platform-wide — it records a verification decision and never auto-changes a
    rule (AGENTS.md *User Feedback Queue*: no auto-publish, no bypass of analyst
    review). The feedback RLS policy therefore also admits the analyst path
    (no tenant GUC set), unlike the standard tenant-owned tables.
    """

    __tablename__ = "feedback"

    feedback_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenant.tenant_id"), nullable=False, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("project.project_id"), nullable=True
    )
    evaluation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    submitted_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("app_user.user_id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        _feedback_status_enum, default="open", nullable=False
    )
    disposition_note: Mapped[str | None] = mapped_column(String, nullable=True)
    dispositioned_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    dispositioned_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TenantBilling(Base):
    """A tenant's Stripe billing state and derived entitlement (S03-01, SAAS-03).

    Exactly one row per tenant (``tenant_id`` unique). The ``plan`` and ``status``
    are the tenant's *entitlement* and are written ONLY from verified Stripe
    webhook events (never from a browser/checkout redirect — webhooks are the sole
    source of truth). Tenant-owned, so it carries RLS like the other tenant tables.
    """

    __tablename__ = "tenant_billing"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenant.tenant_id"), nullable=False, unique=True
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    plan: Mapped[str] = mapped_column(
        _billing_plan_enum, default="free", nullable=False
    )
    status: Mapped[str] = mapped_column(
        _billing_status_enum, default="none", nullable=False
    )
    current_period_end: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class UsageRecord(Base):
    """One metered-action event for a tenant (S03-03, SAAS-03).

    Append-only: a new row is inserted for every metered action (e.g. each
    successful project evaluation). Aggregates (counts per period) are derived
    on read — this keeps the write path trivial, audit-friendly, and easily
    back-filled if the metering hook ever misses an event. The event-log
    approach was chosen over a per-period counter because:

    - **Auditability**: every billable event is individually visible with its
      timestamp, enabling dispute resolution without reconstructing history.
    - **Simplicity**: no period-management logic; the insert is a single
      ``session.add``; aggregation is a single SQL GROUP-BY on read.
    - **Flexibility**: ad-hoc period windows (monthly, rolling-30-day, etc.)
      are expressible in one query against the raw events.

    Tenant-owned and RLS-protected (ADR-0002) just like ``evaluation``.
    """

    __tablename__ = "usage_record"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenant.tenant_id"), nullable=False, index=True
    )
    metric: Mapped[str] = mapped_column(_usage_metric_enum, nullable=False)
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )


class ProcessedStripeEvent(Base):
    """Idempotency ledger of handled Stripe webhook events (S03-01).

    Stripe retries webhook deliveries, so each ``event_id`` is recorded once and a
    redelivery of the same id is a no-op. Platform-global (not tenant-owned): the
    Stripe event id is unique across the account and the webhook arrives unauth'd.
    """

    __tablename__ = "processed_stripe_event"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    processed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class RulePublication(Base):
    """Governance trail for promoting a rule between lifecycle statuses (S05-02).

    Records the proposal and its decision — the audit log (ADR-0004) captures
    the *event* of each transition, while this table captures the *case* (who
    proposed what, who decided, when, why). Platform-global (no tenant scope):
    rules are global per ADR-0002. Separation-of-duties (proposer ≠ approver)
    is enforced at the router layer; the lifecycle invariants are enforced here
    by ``status``/``target_status`` constraints + indexed lookups by ``rule_id``.
    """

    __tablename__ = "rule_publication"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    rule_version: Mapped[str] = mapped_column(String(20), nullable=False)
    target_status: Mapped[str] = mapped_column(_publication_target_enum, nullable=False)
    status: Mapped[str] = mapped_column(
        _publication_status_enum, default="proposed", nullable=False
    )
    proposed_by: Mapped[str] = mapped_column(String(320), nullable=False)
    proposed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    decided_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(String, nullable=True)
