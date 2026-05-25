"""Tests for the regulatory rule ingestion pipeline (T02-06).

Exercises load_rules_from_json, load_rules_from_csv, and normalize against
the non-authoritative SAMPLE templates in templates/ingestion/.

All DB operations run against in-memory SQLite so no PostgreSQL is needed.
Package import paths are configured by tests/conftest.py.

IMPORTANT: the sample templates used here are NON-AUTHORITATIVE and exist
only to exercise the pipeline in tests. They do not represent real Texas
regulatory requirements.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ipermit_persistence import Base
from ipermit_regulatory.ingest import (
    IngestError,
    load_rules_from_csv,
    load_rules_from_json,
    normalize,
)
from ipermit_regulatory.models import RegulatoryCitation, RegulatoryRule
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "templates" / "ingestion"
JSON_TEMPLATE = TEMPLATE_DIR / "rule-template.json"
CSV_TEMPLATE = TEMPLATE_DIR / "rule-template.csv"


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# ---------------------------------------------------------------------------
# JSON template — validates + persists
# ---------------------------------------------------------------------------


def test_load_json_template_validates_and_persists(session: Session) -> None:
    """The JSON sample template loads cleanly into SQLite."""
    results = load_rules_from_json(JSON_TEMPLATE, session)
    session.commit()

    assert len(results) == 1
    rule_id = results[0]["rule_id"]
    row = session.scalar(
        select(RegulatoryRule).where(RegulatoryRule.rule_id == rule_id)
    )
    assert row is not None
    assert row.version == results[0]["version"]


def test_load_json_template_creates_citations(session: Session) -> None:
    """Citations from the JSON template are persisted as child rows."""
    results = load_rules_from_json(JSON_TEMPLATE, session)
    session.commit()

    rule_id = results[0]["rule_id"]
    version = results[0]["version"]
    cits = session.scalars(
        select(RegulatoryCitation).where(
            RegulatoryCitation.rule_id == rule_id,
            RegulatoryCitation.version == version,
        )
    ).all()
    expected = len(results[0]["provenance"]["source_citations"])
    assert len(cits) == expected


# ---------------------------------------------------------------------------
# JSON dry_run — validates but writes nothing
# ---------------------------------------------------------------------------


def test_json_dry_run_validates_but_writes_nothing(session: Session) -> None:
    """dry_run=True validates without persisting any rows."""
    results = load_rules_from_json(JSON_TEMPLATE, session, dry_run=True)
    session.commit()

    assert len(results) == 1
    count = session.scalar(
        select(RegulatoryRule).where(RegulatoryRule.rule_id == results[0]["rule_id"])
    )
    assert count is None  # nothing written


def test_json_dry_run_works_without_session() -> None:
    """dry_run with no session must not raise."""
    results = load_rules_from_json(JSON_TEMPLATE, dry_run=True)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# CSV template — validates + persists
# ---------------------------------------------------------------------------


def test_load_csv_template_validates_and_persists(session: Session) -> None:
    """The CSV sample template loads cleanly into SQLite."""
    results = load_rules_from_csv(CSV_TEMPLATE, session)
    session.commit()

    assert len(results) == 1
    rule_id = results[0]["rule_id"]
    row = session.scalar(
        select(RegulatoryRule).where(RegulatoryRule.rule_id == rule_id)
    )
    assert row is not None


def test_load_csv_template_creates_citations(session: Session) -> None:
    """Citations from the CSV template are persisted as child rows."""
    results = load_rules_from_csv(CSV_TEMPLATE, session)
    session.commit()

    rule_id = results[0]["rule_id"]
    version = results[0]["version"]
    cits = session.scalars(
        select(RegulatoryCitation).where(
            RegulatoryCitation.rule_id == rule_id,
            RegulatoryCitation.version == version,
        )
    ).all()
    assert len(cits) >= 1


# ---------------------------------------------------------------------------
# CSV dry_run
# ---------------------------------------------------------------------------


def test_csv_dry_run_validates_but_writes_nothing(session: Session) -> None:
    """CSV dry_run=True validates without persisting any rows."""
    results = load_rules_from_csv(CSV_TEMPLATE, session, dry_run=True)
    session.commit()

    assert len(results) == 1
    rule_id = results[0]["rule_id"]
    count = session.scalar(
        select(RegulatoryRule).where(RegulatoryRule.rule_id == rule_id)
    )
    assert count is None  # nothing written


# ---------------------------------------------------------------------------
# Broken row — raises IngestError with useful message
# ---------------------------------------------------------------------------


def test_broken_json_row_raises_ingest_error_with_row_and_field(
    tmp_path: Path,
) -> None:
    """A JSON row missing required fields raises IngestError naming row + field."""
    bad = [{"rule_id": "sample-bad-row", "version": "1.0.0"}]
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps(bad))

    with pytest.raises(IngestError) as exc_info:
        load_rules_from_json(bad_file, dry_run=True)

    msg = str(exc_info.value)
    # Must name the row
    assert "row 0" in msg
    # Must name the missing field or show a path
    assert any(kw in msg for kw in ("title", "triggers", "outputs", "required"))


def test_broken_csv_row_raises_ingest_error(tmp_path: Path) -> None:
    """A CSV row with an invalid confidence_tier raises IngestError."""
    header = "rule_id,version,title,permit_name,jurisdiction_level,jurisdiction_id,"
    header += "source_agency,applicable_project_types,confidence_tier,status,"
    header += "last_verified,reviewer,reviewer_notes,source_citations,"
    header += "triggers,outputs,explanations,sequencing,supersedes,superseded_by,"
    header += "known_unknowns,advisories,tags,notes"

    citations = json.dumps([{"citation_type": "website", "reference": "SAMPLE REF"}])
    triggers = json.dumps({"field": "project.linear", "operator": "=", "value": True})
    outputs = json.dumps(
        {"permits": [{"name": "Demo Permit", "agency": "Demo Agency"}]}
    )
    explanations = json.dumps({"trigger_explanation": "SAMPLE explanation."})

    row = (
        f"bad-rule-id-test,1.0.0,Bad Rule,Bad Permit,state,us-tx,"
        f"Bad Agency,transmission_line,NOTANUMBER,draft,"
        f"2026-01-01,analyst,,{citations},"
        f"{triggers},{outputs},{explanations},,,,,"
        ",,"
    )

    bad_file = tmp_path / "bad.csv"
    bad_file.write_text(header + "\n" + row + "\n")

    with pytest.raises((IngestError, ValueError)):
        load_rules_from_csv(bad_file, dry_run=True)


# ---------------------------------------------------------------------------
# normalize helper
# ---------------------------------------------------------------------------


def test_normalize_maps_kebab_jurisdiction_level() -> None:
    """normalize accepts kebab-case jurisdiction_level and maps to snake_case."""
    row = _minimal_row()
    row["jurisdiction_level"] = "river-authority"
    doc = normalize(row)
    assert doc["jurisdiction_level"] == "river_authority"


def test_normalize_splits_pipe_project_types() -> None:
    """normalize expands pipe-separated applicable_project_types to a list."""
    row = _minimal_row()
    row["applicable_project_types"] = "transmission_line|linear_general"
    doc = normalize(row)
    assert doc["applicable_project_types"] == ["transmission_line", "linear_general"]


def test_normalize_coerces_confidence_tier_to_int() -> None:
    """normalize converts a string confidence_tier to an integer."""
    row = _minimal_row()
    row["confidence_tier"] = "3"
    doc = normalize(row)
    assert doc["confidence_tier"] == 3
    assert isinstance(doc["confidence_tier"], int)


def test_normalize_omits_blank_optional_fields() -> None:
    """normalize does not include blank optional fields in the output."""
    row = _minimal_row()
    row["permit_code"] = ""
    row["effective_from"] = ""
    doc = normalize(row)
    assert "permit_code" not in doc
    assert "effective_from" not in doc


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _minimal_row() -> dict:
    """Return a minimal but valid ingest row for normalize() testing."""
    return {
        "rule_id": "sample-state-pipeline-demo-permit",
        "version": "1.0.0",
        "title": "Sample Rule for normalize() tests",
        "permit_name": "Sample Demo Permit",
        "jurisdiction_level": "state",
        "jurisdiction_id": "us-tx",
        "source_agency": "Sample Agency — Not Real",
        "applicable_project_types": "transmission_line",
        "confidence_tier": "3",
        "status": "draft",
        "last_verified": "2026-01-01",
        "source_citations": json.dumps(
            [
                {
                    "citation_type": "website",
                    "reference": "SAMPLE REF — NOT AUTHORITATIVE",
                }
            ]
        ),
        "triggers": json.dumps(
            {"field": "project.linear", "operator": "=", "value": True}
        ),
        "outputs": json.dumps(
            {"permits": [{"name": "Sample Demo", "agency": "Sample Agency — Not Real"}]}
        ),
        "explanations": json.dumps(
            {"trigger_explanation": "SAMPLE ONLY — analyst verification required."}
        ),
    }
