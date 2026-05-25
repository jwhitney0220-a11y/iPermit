"""ORM models for the regulatory intelligence schema (T02-02).

Implements the canonical rule object (T00-01,
docs/specs/schemas/rule-object.schema.json) as relational tables. The full
recursive trigger tree, outputs, sequencing, and explanation fields are stored
in a ``document`` JSON column — the rules engine parses those at evaluation
time. Queryable top-level fields are promoted to real columns so the ingestion
pipeline (T02-06) and freshness tracker (T02-07) can filter without parsing
JSON.

The ``RegulatoryCitation`` child table mirrors ``provenance.source_citations``
from the canonical rule object. It is a real table (not JSON) because
source-tracking (T02-05) and freshness (T02-07) need to query it directly.

The ``SourceCheck`` table (T02-05) records a point-in-time verification event
against a specific citation reference. Multiple checks may exist per citation.
Freshness scoring (T02-07) reads these records independently of confidence tier.

Both tables use ``Enum(native_enum=False)`` (VARCHAR + CHECK) and portable
``JSON`` column types so the identical schema works on SQLite (unit tests) and
PostgreSQL (production), per ADR-0005.
"""

from __future__ import annotations

import datetime

from ipermit_persistence import Base
from sqlalchemy import Boolean, Date, Enum, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

# ---------------------------------------------------------------------------
# Enum value sets — keep in sync with rule-object.schema.json
# ---------------------------------------------------------------------------

RULE_JURISDICTION_LEVELS = (
    "federal",
    "state",
    "county",
    "municipality",
    "etj",
    "utility_district",
    "drainage_district",
    "river_authority",
    "special",
)

RULE_STATUSES = ("draft", "published", "effective", "archived")

CITATION_TYPES = (
    "statute",
    "regulation",
    "ordinance",
    "agency_guidance",
    "form",
    "website",
)

# native_enum=False → VARCHAR + CHECK, portable SQLite <-> PostgreSQL.
_rule_level_enum = Enum(
    *RULE_JURISDICTION_LEVELS,
    name="rule_jurisdiction_level",
    native_enum=False,
)
_rule_status_enum = Enum(
    *RULE_STATUSES,
    name="rule_status",
    native_enum=False,
)
_citation_type_enum = Enum(
    *CITATION_TYPES,
    name="citation_type",
    native_enum=False,
)


class RegulatoryRule(Base):
    """Queryable projection of a canonical rule object.

    Primary key is ``(rule_id, version)`` — one row per versioned rule. The
    full canonical document (triggers, outputs, sequencing, explanations, …)
    lives in ``document``; promoted columns support indexed queries.

    ``jurisdiction_id`` is stored as a plain string that matches the registry
    in the ``jurisdiction`` table; a FK is not declared here because rules
    referencing federal / placeholder jurisdictions may be loaded before the
    jurisdiction hierarchy is populated.
    """

    __tablename__ = "regulatory_rule"

    rule_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    version: Mapped[str] = mapped_column(String(20), primary_key=True)

    title: Mapped[str] = mapped_column(String(80), nullable=False)
    permit_name: Mapped[str] = mapped_column(String(200), nullable=False)
    permit_code: Mapped[str | None] = mapped_column(String(80), nullable=True)

    jurisdiction_level: Mapped[str] = mapped_column(_rule_level_enum, nullable=False)
    jurisdiction_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_agency: Mapped[str] = mapped_column(String(300), nullable=False)

    confidence_tier: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(_rule_status_enum, nullable=False)
    effective_from: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)

    last_verified: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # JSON list of project-type token strings (portable across SQLite/PG).
    applicable_project_types: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )

    # Full canonical rule document stored as JSON.
    document: Mapped[dict] = mapped_column(JSON, nullable=False)

    citations: Mapped[list[RegulatoryCitation]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="RegulatoryCitation.id",
    )


class RegulatoryCitation(Base):
    """A single source citation from ``provenance.source_citations``.

    Child of ``RegulatoryRule`` via the composite FK ``(rule_id, version)``.
    Modelled as a real table so source-tracking (T02-05) and freshness
    (T02-07) can query individual citations directly.
    """

    __tablename__ = "regulatory_citation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)

    citation_type: Mapped[str] = mapped_column(_citation_type_enum, nullable=False)
    reference: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    retrieved_at: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_id", "version"],
            ["regulatory_rule.rule_id", "regulatory_rule.version"],
            name="fk_regulatory_citation_rule",
        ),
    )

    rule: Mapped[RegulatoryRule] = relationship(back_populates="citations")


class SourceCheck(Base):
    """A point-in-time verification event against a citation reference (T02-05).

    Records the outcome of checking whether a citation's URL is still reachable
    and whether the underlying source has changed. Multiple checks may exist per
    (rule_id, version, reference) triple, ordered by ``checked_at``.

    The composite FK ``(rule_id, version)`` references ``RegulatoryRule`` — the
    same pattern used by ``RegulatoryCitation`` — so checks are automatically
    cascaded when a rule version is deleted.

    Freshness scoring (T02-07) reads these records independently of
    ``confidence_tier``; a Tier-1 rule that has not been checked for 365+ days
    is stale regardless of its tier.
    """

    __tablename__ = "source_check"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)

    # The citation reference string this check was performed against.
    reference: Mapped[str] = mapped_column(String, nullable=False)

    checked_at: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    # None means the check did not attempt an HTTP request (e.g. manual check).
    url_reachable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # True if the analyst observed the form or submission process changed.
    form_changed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_id", "version"],
            ["regulatory_rule.rule_id", "regulatory_rule.version"],
            name="fk_source_check_rule",
        ),
    )
