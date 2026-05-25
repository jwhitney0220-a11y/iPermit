"""Convert, validate, and traverse jurisdiction records (T02-01).

Bridges the canonical jurisdiction record (T00-08 JSON shape) and the ORM
models. Records are validated against
docs/specs/schemas/jurisdiction-record.schema.json before they enter the
database, so the database never holds a record that violates the standard.
"""

from __future__ import annotations

import datetime
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Jurisdiction, JurisdictionAlias

_SCHEMA_REL = "docs/specs/schemas/jurisdiction-record.schema.json"


def _repo_root() -> Path:
    """Find the repo root by walking up to the canonical schema file."""
    for parent in Path(__file__).resolve().parents:
        if (parent / _SCHEMA_REL).is_file():
            return parent
    raise FileNotFoundError(f"could not locate {_SCHEMA_REL}")


@lru_cache(maxsize=1)
def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads((_repo_root() / _SCHEMA_REL).read_text())
    return jsonschema.Draft202012Validator(schema)


def validate_record(data: dict[str, Any]) -> None:
    """Raise jsonschema.ValidationError if the record violates T00-08."""
    _validator().validate(data)


def _date(value: str | None) -> datetime.date | None:
    return datetime.date.fromisoformat(value) if value else None


def from_record(data: dict[str, Any]) -> Jurisdiction:
    """Build a Jurisdiction ORM object from a (validated) canonical record."""
    fips = data.get("fips", {})
    j = Jurisdiction(
        jurisdiction_id=data["jurisdiction_id"],
        canonical_name=data["canonical_name"],
        jurisdiction_level=data["jurisdiction_level"],
        parent_jurisdiction_id=data.get("parent_jurisdiction_id"),
        fips_state=fips.get("fips_state"),
        fips_county=fips.get("fips_county"),
        fips_place=fips.get("fips_place"),
        geometry_ref=data.get("geometry_ref"),
        active_from=_date(data["active_from"]),
        active_to=_date(data.get("active_to")),
        replaced_by=list(data.get("replaced_by", [])),
        replaced_from=list(data.get("replaced_from", [])),
        notes=data.get("notes"),
    )
    j.aliases = [_alias_from(a) for a in data.get("aliases", [])]
    return j


def _alias_from(a: dict[str, Any]) -> JurisdictionAlias:
    return JurisdictionAlias(
        value=a["value"],
        alias_type=a["alias_type"],
        source=a.get("source"),
        date_from=_date(a.get("date_from")),
        date_to=_date(a.get("date_to")),
        notes=a.get("notes"),
    )


def _fips_obj(j: Jurisdiction) -> dict[str, str]:
    keys = (
        ("fips_state", j.fips_state),
        ("fips_county", j.fips_county),
        ("fips_place", j.fips_place),
    )
    return {k: v for k, v in keys if v}


def _alias_obj(a: JurisdictionAlias) -> dict[str, Any]:
    out: dict[str, Any] = {"value": a.value, "alias_type": a.alias_type}
    for key, val in (("source", a.source), ("notes", a.notes)):
        if val:
            out[key] = val
    for key, dt in (("date_from", a.date_from), ("date_to", a.date_to)):
        if dt:
            out[key] = dt.isoformat()
    return out


def to_record(j: Jurisdiction) -> dict[str, Any]:
    """Render an ORM Jurisdiction back into the canonical T00-08 record dict."""
    out: dict[str, Any] = {
        "jurisdiction_id": j.jurisdiction_id,
        "canonical_name": j.canonical_name,
        "jurisdiction_level": j.jurisdiction_level,
        "active_from": j.active_from.isoformat(),
    }
    if j.parent_jurisdiction_id is not None:
        out["parent_jurisdiction_id"] = j.parent_jurisdiction_id
    if j.aliases:
        out["aliases"] = [_alias_obj(a) for a in j.aliases]
    fips = _fips_obj(j)
    if fips:
        out["fips"] = fips
    for key, val in (("geometry_ref", j.geometry_ref), ("notes", j.notes)):
        if val:
            out[key] = val
    if j.active_to:
        out["active_to"] = j.active_to.isoformat()
    for key, arr in (
        ("replaced_by", j.replaced_by),
        ("replaced_from", j.replaced_from),
    ):
        if arr:
            out[key] = list(arr)
    return out


def add_record(session: Session, data: dict[str, Any]) -> Jurisdiction:
    """Validate a canonical record and add it to the session."""
    validate_record(data)
    j = from_record(data)
    session.add(j)
    return j


def ancestors(session: Session, jurisdiction_id: str) -> list[Jurisdiction]:
    """Return the parent chain from immediate parent up to the root (federal)."""
    chain: list[Jurisdiction] = []
    current = session.get(Jurisdiction, jurisdiction_id)
    seen = {jurisdiction_id}
    while current is not None and current.parent_jurisdiction_id is not None:
        parent_id = current.parent_jurisdiction_id
        if parent_id in seen:
            raise ValueError(f"cycle in jurisdiction hierarchy at {parent_id}")
        seen.add(parent_id)
        current = session.get(Jurisdiction, parent_id)
        if current is not None:
            chain.append(current)
    return chain


def all_jurisdictions(session: Session) -> list[Jurisdiction]:
    """Return every jurisdiction ordered by id (deterministic)."""
    return list(
        session.scalars(select(Jurisdiction).order_by(Jurisdiction.jurisdiction_id))
    )
