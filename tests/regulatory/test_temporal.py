"""Tests for temporal rule activation logic (T02-04).

Covers is_governing, effective_rule, and effective_ruleset against an
in-memory SQLite database.  Rule fixtures mirror the worked example in
docs/specs/temporal-versioning.md §4.2 plus extra draft/published/future
cases to verify those are never returned.

Scenario:
  rule_id "tx-county-floodplain-development-permit"
    v1.0.0  archived  2024-01-01 → 2025-12-31
    v2.0.0  effective 2025-12-31 → (open)

  rule_id "tx-county-flood-draft"
    v1.0.0  draft     2024-01-01 → (open)   — must NEVER govern

  rule_id "tx-county-flood-published"
    v1.0.0  published 2027-01-01 → (open)   — future, must NEVER govern
"""

from __future__ import annotations

import datetime

import pytest
from ipermit_persistence import Base
from ipermit_regulatory import RegulatoryRule
from ipermit_regulatory.temporal import (
    effective_rule,
    effective_ruleset,
    is_governing,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

RULE_ID = "tx-county-floodplain-development-permit"
DRAFT_ID = "tx-county-flood-draft"
PUBLISHED_ID = "tx-county-flood-published"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_rule(
    rule_id: str,
    version: str,
    status: str,
    effective_from: datetime.date | None,
    effective_to: datetime.date | None,
) -> RegulatoryRule:
    """Build a minimal RegulatoryRule ORM object for testing."""
    return RegulatoryRule(
        rule_id=rule_id,
        version=version,
        title="Test Rule",
        permit_name="Test Permit",
        jurisdiction_level="county",
        jurisdiction_id="tx-county-travis",
        source_agency="Test Agency",
        confidence_tier=1,
        status=status,
        effective_from=effective_from,
        effective_to=effective_to,
        last_verified=datetime.date(2024, 1, 1),
        applicable_project_types=["linear_general"],
        document={},
    )


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def populated_session(session: Session) -> Session:
    """Session with the §4.2 fixture rules plus draft/published rules."""
    d = datetime.date
    session.add_all(
        [
            # §4.2 v1 — archived, window ends 2025-12-31
            _make_rule(RULE_ID, "1.0.0", "archived", d(2024, 1, 1), d(2025, 12, 31)),
            # §4.2 v2 — effective, window starts 2025-12-31
            _make_rule(RULE_ID, "2.0.0", "effective", d(2025, 12, 31), None),
            # draft rule — must never govern
            _make_rule(DRAFT_ID, "1.0.0", "draft", d(2024, 1, 1), None),
            # published future rule — must never govern
            _make_rule(PUBLISHED_ID, "1.0.0", "published", d(2027, 1, 1), None),
        ]
    )
    session.commit()
    return session


# ---------------------------------------------------------------------------
# is_governing — pure predicate tests
# ---------------------------------------------------------------------------


def test_is_governing_effective_in_window() -> None:
    rule = _make_rule(
        RULE_ID,
        "1.0.0",
        "effective",
        datetime.date(2024, 1, 1),
        datetime.date(2025, 12, 31),
    )
    assert is_governing(rule, datetime.date(2025, 6, 15))


def test_is_governing_archived_in_window() -> None:
    rule = _make_rule(
        RULE_ID,
        "1.0.0",
        "archived",
        datetime.date(2024, 1, 1),
        datetime.date(2025, 12, 31),
    )
    assert is_governing(rule, datetime.date(2024, 6, 1))


def test_is_governing_draft_is_never_governing() -> None:
    rule = _make_rule(DRAFT_ID, "1.0.0", "draft", datetime.date(2024, 1, 1), None)
    assert not is_governing(rule, datetime.date(2025, 1, 1))


def test_is_governing_published_is_never_governing() -> None:
    rule = _make_rule(
        PUBLISHED_ID, "1.0.0", "published", datetime.date(2024, 1, 1), None
    )
    assert not is_governing(rule, datetime.date(2025, 1, 1))


def test_is_governing_before_effective_from() -> None:
    rule = _make_rule(RULE_ID, "1.0.0", "effective", datetime.date(2024, 1, 1), None)
    assert not is_governing(rule, datetime.date(2023, 12, 31))


def test_is_governing_after_effective_to() -> None:
    rule = _make_rule(
        RULE_ID,
        "1.0.0",
        "archived",
        datetime.date(2024, 1, 1),
        datetime.date(2025, 12, 31),
    )
    assert not is_governing(rule, datetime.date(2026, 1, 1))


def test_is_governing_on_effective_from_boundary() -> None:
    """effective_from is inclusive."""
    rule = _make_rule(RULE_ID, "1.0.0", "effective", datetime.date(2025, 12, 31), None)
    assert is_governing(rule, datetime.date(2025, 12, 31))


def test_is_governing_on_effective_to_boundary() -> None:
    """effective_to is inclusive (spec §4 boundary; both endpoints inclusive)."""
    rule = _make_rule(
        RULE_ID,
        "1.0.0",
        "archived",
        datetime.date(2024, 1, 1),
        datetime.date(2025, 12, 31),
    )
    assert is_governing(rule, datetime.date(2025, 12, 31))


def test_is_governing_open_ended() -> None:
    rule = _make_rule(RULE_ID, "2.0.0", "effective", datetime.date(2025, 12, 31), None)
    assert is_governing(rule, datetime.date(2026, 6, 1))


def test_is_governing_null_effective_from_is_not_governing() -> None:
    rule = _make_rule(RULE_ID, "1.0.0", "effective", None, None)
    assert not is_governing(rule, datetime.date(2025, 6, 1))


# ---------------------------------------------------------------------------
# effective_rule — DB query tests (§4.2 worked example)
# ---------------------------------------------------------------------------


def test_effective_rule_v1_mid_2025(populated_session: Session) -> None:
    """Project A: D=2025-06-15 → v1.0.0 (only candidate)."""
    result = effective_rule(populated_session, RULE_ID, datetime.date(2025, 6, 15))
    assert result is not None
    assert result.version == "1.0.0"


def test_effective_rule_v2_in_2026(populated_session: Session) -> None:
    """Project B: D=2026-02-10 → v2.0.0 (v1 expired)."""
    result = effective_rule(populated_session, RULE_ID, datetime.date(2026, 2, 10))
    assert result is not None
    assert result.version == "2.0.0"


def test_effective_rule_tie_broken_to_v2_on_boundary(
    populated_session: Session,
) -> None:
    """Project C: D=2025-12-31 → both match; latest effective_from → v2.0.0."""
    result = effective_rule(populated_session, RULE_ID, datetime.date(2025, 12, 31))
    assert result is not None
    assert result.version == "2.0.0"


def test_effective_rule_replay_past_date_returns_v1(populated_session: Session) -> None:
    """Replay of Project A at a later wall-clock time: D still 2025-06-15 → v1.0.0."""
    result = effective_rule(populated_session, RULE_ID, datetime.date(2025, 6, 15))
    assert result is not None
    assert result.version == "1.0.0"


def test_effective_rule_before_any_version_returns_none(
    populated_session: Session,
) -> None:
    result = effective_rule(populated_session, RULE_ID, datetime.date(2023, 12, 31))
    assert result is None


def test_effective_rule_draft_never_returned(populated_session: Session) -> None:
    result = effective_rule(populated_session, DRAFT_ID, datetime.date(2025, 6, 15))
    assert result is None


def test_effective_rule_published_future_never_returned(
    populated_session: Session,
) -> None:
    # Even querying well into the future when effective_from has passed,
    # published status must not govern (only effective/archived governs).
    result = effective_rule(populated_session, PUBLISHED_ID, datetime.date(2028, 1, 1))
    assert result is None


def test_effective_rule_unknown_rule_id_returns_none(
    populated_session: Session,
) -> None:
    result = effective_rule(
        populated_session, "tx-nonexistent-rule", datetime.date(2025, 6, 15)
    )
    assert result is None


# ---------------------------------------------------------------------------
# effective_ruleset — multi-rule set query tests
# ---------------------------------------------------------------------------


def test_effective_ruleset_mid_2025_returns_v1(populated_session: Session) -> None:
    """Only RULE_ID should appear; v1.0.0 governs on 2025-06-15."""
    ruleset = effective_ruleset(populated_session, datetime.date(2025, 6, 15))
    ids = {r.rule_id for r in ruleset}
    assert RULE_ID in ids
    assert DRAFT_ID not in ids
    assert PUBLISHED_ID not in ids
    rule = next(r for r in ruleset if r.rule_id == RULE_ID)
    assert rule.version == "1.0.0"


def test_effective_ruleset_2026_returns_v2(populated_session: Session) -> None:
    ruleset = effective_ruleset(populated_session, datetime.date(2026, 2, 10))
    rule = next((r for r in ruleset if r.rule_id == RULE_ID), None)
    assert rule is not None
    assert rule.version == "2.0.0"


def test_effective_ruleset_excludes_draft_and_published(
    populated_session: Session,
) -> None:
    ruleset = effective_ruleset(populated_session, datetime.date(2025, 6, 15))
    rule_ids = {r.rule_id for r in ruleset}
    assert DRAFT_ID not in rule_ids
    assert PUBLISHED_ID not in rule_ids


def test_effective_ruleset_sorted_by_rule_id(populated_session: Session) -> None:
    ruleset = effective_ruleset(populated_session, datetime.date(2025, 6, 15))
    ids = [r.rule_id for r in ruleset]
    assert ids == sorted(ids)


def test_effective_ruleset_empty_when_nothing_governs(session: Session) -> None:
    ruleset = effective_ruleset(session, datetime.date(2025, 6, 15))
    assert ruleset == []
