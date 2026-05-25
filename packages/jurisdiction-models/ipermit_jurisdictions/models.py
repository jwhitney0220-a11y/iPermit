"""ORM models for the jurisdiction hierarchy (T02-01).

Implements the canonical jurisdiction record (T00-08,
docs/specs/schemas/jurisdiction-record.schema.json) as relational tables. The
``replaced_by`` / ``replaced_from`` lineage arrays are stored as JSON (portable
across SQLite for tests and PostgreSQL in production). Geometry is a string
reference only — the spatial store is T05-01's concern.
"""

from __future__ import annotations

import datetime

from ipermit_persistence import Base
from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

JURISDICTION_LEVELS = (
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
ALIAS_TYPES = ("abbreviation", "historical", "colloquial", "misspelling")

# native_enum=False renders as VARCHAR + CHECK — portable SQLite <-> PostgreSQL.
_level_enum = Enum(*JURISDICTION_LEVELS, name="jurisdiction_level", native_enum=False)
_alias_enum = Enum(*ALIAS_TYPES, name="alias_type", native_enum=False)


class Jurisdiction(Base):
    """A single jurisdiction record (county, municipality, district, ...)."""

    __tablename__ = "jurisdiction"

    jurisdiction_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    jurisdiction_level: Mapped[str] = mapped_column(_level_enum, nullable=False)
    parent_jurisdiction_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("jurisdiction.jurisdiction_id"), nullable=True
    )
    fips_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    fips_county: Mapped[str | None] = mapped_column(String(5), nullable=True)
    fips_place: Mapped[str | None] = mapped_column(String(7), nullable=True)
    geometry_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    active_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    active_to: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    replaced_by: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    replaced_from: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    aliases: Mapped[list[JurisdictionAlias]] = relationship(
        back_populates="jurisdiction",
        cascade="all, delete-orphan",
        order_by="JurisdictionAlias.id",
    )


class JurisdictionAlias(Base):
    """An alternate name observed for a jurisdiction (T00-08 alias)."""

    __tablename__ = "jurisdiction_alias"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jurisdiction_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("jurisdiction.jurisdiction_id"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    alias_type: Mapped[str] = mapped_column(_alias_enum, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    date_from: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    jurisdiction: Mapped[Jurisdiction] = relationship(back_populates="aliases")
