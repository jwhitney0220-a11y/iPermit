"""Unit tests for the regulatory intelligence schema (T02-02 / T02-03).

Run against in-memory SQLite so CI needs no PostgreSQL. The fixtures load the
canonical T00-01 example document to keep the ORM aligned with the schema.
Package import paths are set up in tests/conftest.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from ipermit_persistence import Base
from ipermit_regulatory import (
    ConfidenceTier,
    RegulatoryCitation,
    add_rule,
    get_rule,
    tier_description,
    to_document,
    validate_tier,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = json.loads(
    (ROOT / "docs/specs/examples/rule-object-example.json").read_text()
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# ---------------------------------------------------------------------------
# T02-02 — ORM / table tests
# ---------------------------------------------------------------------------


def test_create_all_builds_regulatory_tables(session: Session) -> None:
    assert {"regulatory_rule", "regulatory_citation"} <= set(Base.metadata.tables)


def test_add_rule_round_trip_document(session: Session) -> None:
    add_rule(session, EXAMPLE)
    session.commit()

    stored = get_rule(session, EXAMPLE["rule_id"], EXAMPLE["version"])
    assert stored is not None

    doc = to_document(stored)
    assert doc["rule_id"] == EXAMPLE["rule_id"]
    assert doc["version"] == EXAMPLE["version"]
    assert doc["title"] == EXAMPLE["title"]


def test_add_rule_promotes_columns_correctly(session: Session) -> None:
    add_rule(session, EXAMPLE)
    session.commit()

    stored = get_rule(session, EXAMPLE["rule_id"], EXAMPLE["version"])
    assert stored is not None
    assert stored.rule_id == EXAMPLE["rule_id"]
    assert stored.version == EXAMPLE["version"]
    assert stored.title == EXAMPLE["title"]
    assert stored.permit_name == EXAMPLE["permit_name"]
    assert stored.permit_code == EXAMPLE.get("permit_code")
    assert stored.jurisdiction_level == EXAMPLE["jurisdiction_level"]
    assert stored.jurisdiction_id == EXAMPLE["jurisdiction_id"]
    assert stored.source_agency == EXAMPLE["source_agency"]
    assert stored.confidence_tier == EXAMPLE["confidence_tier"]
    assert stored.status == EXAMPLE["status"]
    assert stored.applicable_project_types == EXAMPLE["applicable_project_types"]
    assert stored.reviewer == EXAMPLE["provenance"].get("reviewer")


def test_citations_persisted_with_correct_count(session: Session) -> None:
    add_rule(session, EXAMPLE)
    session.commit()

    stored = get_rule(session, EXAMPLE["rule_id"], EXAMPLE["version"])
    assert stored is not None

    expected_count = len(EXAMPLE["provenance"]["source_citations"])
    assert len(stored.citations) == expected_count

    expected_types = {
        c["citation_type"] for c in EXAMPLE["provenance"]["source_citations"]
    }
    actual_types = {c.citation_type for c in stored.citations}
    assert actual_types == expected_types


def test_invalid_rule_raises_validation_error(session: Session) -> None:
    bad = {"rule_id": "us-federal-cwa-section-404-usace-permit"}  # missing required
    with pytest.raises(jsonschema.ValidationError):
        add_rule(session, bad)


def test_citation_child_rows_have_correct_fk(session: Session) -> None:
    add_rule(session, EXAMPLE)
    session.commit()

    cits = session.query(RegulatoryCitation).all()
    for c in cits:
        assert c.rule_id == EXAMPLE["rule_id"]
        assert c.version == EXAMPLE["version"]


# ---------------------------------------------------------------------------
# T02-03 — Confidence tier tests
# ---------------------------------------------------------------------------


def test_confidence_tier_enum_values() -> None:
    assert ConfidenceTier.VERIFIED == 1
    assert ConfidenceTier.PARTIAL == 2
    assert ConfidenceTier.INFORMATIONAL == 3


def test_tier_description_returns_strings() -> None:
    for tier in (1, 2, 3):
        desc = tier_description(tier)
        assert isinstance(desc, str)
        assert len(desc) > 0


def test_tier_description_contains_tier_semantics() -> None:
    assert "Tier 1" in tier_description(1)
    assert "Tier 2" in tier_description(2)
    assert "Tier 3" in tier_description(3)


def test_validate_tier_accepts_valid_values() -> None:
    for tier in (1, 2, 3):
        validate_tier(tier)  # should not raise


def test_validate_tier_rejects_out_of_range() -> None:
    for bad in (0, 4, -1, 99):
        with pytest.raises(ValueError):
            validate_tier(bad)


def test_tier_description_rejects_invalid_tier() -> None:
    with pytest.raises(ValueError):
        tier_description(0)
