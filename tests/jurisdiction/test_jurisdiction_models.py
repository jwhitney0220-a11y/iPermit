"""Unit tests for the jurisdiction hierarchy DB (T02-01).

Run against in-memory SQLite so CI needs no PostgreSQL. The fixtures load the
real T00-08 example records to keep the ORM aligned with the canonical schema.
Package import paths are set up in tests/conftest.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from ipermit_jurisdictions import (
    Jurisdiction,
    add_record,
    ancestors,
    to_record,
    validate_record,
)
from ipermit_persistence import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = json.loads(
    (ROOT / "docs/specs/examples/jurisdiction-record-examples.json").read_text()
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _by_id(jid: str) -> dict:
    return next(r for r in EXAMPLES if r["jurisdiction_id"] == jid)


def test_schema_create_all_builds_both_tables(session: Session) -> None:
    assert {"jurisdiction", "jurisdiction_alias"} <= set(Base.metadata.tables)


def test_add_and_roundtrip_record(session: Session) -> None:
    for record in EXAMPLES:
        add_record(session, record)
    session.commit()
    for record in EXAMPLES:
        stored = session.get(Jurisdiction, record["jurisdiction_id"])
        assert stored is not None
        rendered = to_record(stored)
        validate_record(rendered)  # round-trip still conforms to T00-08
        assert rendered["jurisdiction_id"] == record["jurisdiction_id"]
        assert rendered["jurisdiction_level"] == record["jurisdiction_level"]


def test_aliases_persist(session: Session) -> None:
    austin = _by_id("us-tx-municipality-austin")
    add_record(session, austin)
    session.commit()
    stored = session.get(Jurisdiction, "us-tx-municipality-austin")
    assert [a["value"] for a in to_record(stored).get("aliases", [])] == [
        a["value"] for a in austin.get("aliases", [])
    ]


def test_ancestors_walk_partial_chain(session: Session) -> None:
    for record in EXAMPLES:
        add_record(session, record)
    session.commit()
    # ETJ -> municipality -> county; the state record (us-tx) is not loaded in
    # the example set, so traversal stops once a parent record is absent.
    chain = ancestors(session, "us-tx-etj-austin")
    assert [j.jurisdiction_id for j in chain] == [
        "us-tx-municipality-austin",
        "us-tx-county-travis",
    ]


def test_invalid_record_rejected(session: Session) -> None:
    bad = {"jurisdiction_id": "us-tx-county-travis"}  # missing required fields
    with pytest.raises(jsonschema.ValidationError):
        add_record(session, bad)
