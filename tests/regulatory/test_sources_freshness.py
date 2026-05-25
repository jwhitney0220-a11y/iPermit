"""Tests for source tracking (T02-05) and data freshness scoring (T02-07).

Run against in-memory SQLite so CI needs no PostgreSQL. Import from the specific
modules rather than the package __init__ to honour the orchestrator ownership rule.
"""

from __future__ import annotations

import datetime
import itertools
import json
from pathlib import Path

import pytest
from ipermit_persistence import Base
from ipermit_regulatory.freshness import (
    CADENCE_DAYS,
    FreshnessLabel,
    freshness_label,
    freshness_score,
    needs_review,
)
from ipermit_regulatory.models import SourceCheck
from ipermit_regulatory.repository import add_rule
from ipermit_regulatory.sources import (
    all_checks_for_rule,
    check_history,
    is_currently_reachable,
    latest_check,
    record_check,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = json.loads(
    (ROOT / "docs/specs/examples/rule-object-example.json").read_text()
)

TODAY = datetime.date(2026, 5, 25)

# Thread-safe counter used to generate unique rule IDs within a test session.
_id_counter = itertools.count(1)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def rule(session: Session):
    """Add and return the canonical example rule."""
    r = add_rule(session, EXAMPLE)
    session.commit()
    return r


# ---------------------------------------------------------------------------
# T02-05 — Source tracking: record_check + latest_check
# ---------------------------------------------------------------------------


def test_source_check_table_created(session: Session) -> None:
    assert "source_check" in Base.metadata.tables


def test_record_check_creates_row(session: Session, rule) -> None:
    check = record_check(
        session,
        rule_id=rule.rule_id,
        version=rule.version,
        reference="33 U.S.C. § 1344",
        checked_at=TODAY,
        url_reachable=True,
        http_status=200,
    )
    session.commit()
    assert check.id is not None
    assert check.rule_id == rule.rule_id
    assert check.version == rule.version
    assert check.reference == "33 U.S.C. § 1344"
    assert check.checked_at == TODAY
    assert check.url_reachable is True
    assert check.http_status == 200


def test_record_check_nullable_fields_default_to_none(session: Session, rule) -> None:
    check = record_check(
        session,
        rule_id=rule.rule_id,
        version=rule.version,
        reference="33 U.S.C. § 1344",
        checked_at=TODAY,
    )
    session.commit()
    assert check.url_reachable is None
    assert check.http_status is None
    assert check.form_changed is None
    assert check.notes is None


def test_latest_check_returns_most_recent(session: Session, rule) -> None:
    older = datetime.date(2026, 1, 1)
    newer = datetime.date(2026, 4, 1)
    ref = "33 U.S.C. § 1344"
    record_check(session, rule.rule_id, rule.version, ref, older, url_reachable=False)
    record_check(session, rule.rule_id, rule.version, ref, newer, url_reachable=True)
    session.commit()

    result = latest_check(session, rule.rule_id, rule.version, ref)
    assert result is not None
    assert result.checked_at == newer
    assert result.url_reachable is True


def test_latest_check_returns_none_when_empty(session: Session, rule) -> None:
    result = latest_check(session, rule.rule_id, rule.version, "nonexistent ref")
    assert result is None


def test_check_history_returns_oldest_first(session: Session, rule) -> None:
    ref = "33 U.S.C. § 1344"
    dates = [
        datetime.date(2026, 3, 1),
        datetime.date(2026, 1, 1),
        datetime.date(2026, 5, 1),
    ]
    for d in dates:
        record_check(session, rule.rule_id, rule.version, ref, d)
    session.commit()

    history = check_history(session, rule.rule_id, rule.version, ref)
    assert [c.checked_at for c in history] == sorted(dates)


def test_all_checks_for_rule_covers_multiple_references(session: Session, rule) -> None:
    record_check(session, rule.rule_id, rule.version, "ref-A", TODAY)
    record_check(session, rule.rule_id, rule.version, "ref-B", TODAY)
    session.commit()

    all_checks = all_checks_for_rule(session, rule.rule_id, rule.version)
    refs = {c.reference for c in all_checks}
    assert "ref-A" in refs
    assert "ref-B" in refs


def test_is_currently_reachable_returns_url_reachable(session: Session, rule) -> None:
    ref = "33 U.S.C. § 1344"
    record_check(session, rule.rule_id, rule.version, ref, TODAY, url_reachable=False)
    session.commit()
    assert is_currently_reachable(session, rule.rule_id, rule.version, ref) is False


def test_is_currently_reachable_returns_none_if_no_checks(
    session: Session, rule
) -> None:
    assert is_currently_reachable(session, rule.rule_id, rule.version, "nope") is None


# ---------------------------------------------------------------------------
# T02-07 — Freshness scoring
# ---------------------------------------------------------------------------


def _make_rule(
    session: Session,
    last_verified: datetime.date,
    tier: int = 1,
) -> object:
    """Produce a rule with configurable last_verified and tier.

    Uses a module-level counter to generate unique rule IDs so that multiple
    calls within the same session do not collide on the composite PK.
    """
    unique_id = f"{EXAMPLE['rule_id']}-{next(_id_counter)}"
    data = {
        **EXAMPLE,
        "rule_id": unique_id,
        "provenance": {
            **EXAMPLE["provenance"],
            "last_verified": last_verified.isoformat(),
        },
        "confidence_tier": tier,
    }
    r = add_rule(session, data)
    session.commit()
    return r


def test_freshness_score_100_when_just_verified(session: Session) -> None:
    rule = _make_rule(session, last_verified=TODAY)
    score = freshness_score(rule, [], TODAY)
    assert score == 100


def test_freshness_score_0_when_past_cadence(session: Session) -> None:
    # Tier 1 cadence is 365 days; verified 400 days ago
    old_date = TODAY - datetime.timedelta(days=400)
    rule = _make_rule(session, last_verified=old_date, tier=1)
    score = freshness_score(rule, [], TODAY)
    assert score == 0


def test_freshness_label_fresh(session: Session) -> None:
    rule = _make_rule(session, last_verified=TODAY)
    score = freshness_score(rule, [], TODAY)
    assert freshness_label(score) == FreshnessLabel.FRESH


def test_freshness_label_aging(session: Session) -> None:
    # Tier 1 cadence = 365 days. 100 days ago → 100 - int(100*100/365) = 73 → aging
    date_100_days_ago = TODAY - datetime.timedelta(days=100)
    rule = _make_rule(session, last_verified=date_100_days_ago, tier=1)
    score = freshness_score(rule, [], TODAY)
    assert 50 <= score < 90
    assert freshness_label(score) == FreshnessLabel.AGING


def test_freshness_label_stale_via_score(session: Session) -> None:
    old_date = TODAY - datetime.timedelta(days=400)
    rule = _make_rule(session, last_verified=old_date, tier=1)
    score = freshness_score(rule, [], TODAY)
    assert freshness_label(score) == FreshnessLabel.STALE


def test_freshness_score_penalised_for_unreachable_url(session: Session) -> None:
    rule = _make_rule(session, last_verified=TODAY, tier=1)
    checks = [
        SourceCheck(
            id=1,
            rule_id=rule.rule_id,
            version=rule.version,
            reference="ref-A",
            checked_at=TODAY,
            url_reachable=False,
            http_status=404,
        )
    ]
    score = freshness_score(rule, checks, TODAY)
    # Base would be 100; penalty for unreachable = 30
    assert score == 70


def test_freshness_score_penalised_for_form_changed(session: Session) -> None:
    rule = _make_rule(session, last_verified=TODAY, tier=1)
    checks = [
        SourceCheck(
            id=1,
            rule_id=rule.rule_id,
            version=rule.version,
            reference="ref-A",
            checked_at=TODAY,
            form_changed=True,
        )
    ]
    score = freshness_score(rule, checks, TODAY)
    # Base 100; penalty for form_changed = 20
    assert score == 80


def test_freshness_score_uses_worst_of_rule_vs_checks(session: Session) -> None:
    # rule last_verified is fresh (TODAY), but check is old → check drives score
    old_date = TODAY - datetime.timedelta(days=400)
    rule = _make_rule(session, last_verified=TODAY, tier=1)
    checks = [
        SourceCheck(
            id=1,
            rule_id=rule.rule_id,
            version=rule.version,
            reference="ref-A",
            checked_at=old_date,
        )
    ]
    score = freshness_score(rule, checks, TODAY)
    assert score == 0  # check is past cadence


def test_freshness_is_independent_of_confidence_tier(session: Session) -> None:
    """Tier 1 has 365-day cadence; Tier 3 has 90-day cadence — different thresholds."""
    old_for_tier3 = TODAY - datetime.timedelta(days=100)
    rule_t1 = _make_rule(session, last_verified=old_for_tier3, tier=1)
    rule_t3 = _make_rule(session, last_verified=old_for_tier3, tier=3)

    score_t1 = freshness_score(rule_t1, [], TODAY)
    score_t3 = freshness_score(rule_t3, [], TODAY)

    # Tier-1 is still in-cadence (100 < 365), Tier-3 is past cadence (100 > 90)
    assert score_t1 > 0
    assert score_t3 == 0


# ---------------------------------------------------------------------------
# T02-07 — needs_review predicate
# ---------------------------------------------------------------------------


def test_needs_review_false_for_fresh_rule(session: Session) -> None:
    rule = _make_rule(session, last_verified=TODAY, tier=1)
    assert needs_review(rule, [], TODAY) is False


def test_needs_review_true_for_stale_tier1_rule(session: Session) -> None:
    """A stale Tier-1 rule must flag as needing review (freshness != confidence)."""
    old_date = TODAY - datetime.timedelta(days=400)
    rule = _make_rule(session, last_verified=old_date, tier=1)
    assert needs_review(rule, [], TODAY) is True


def test_needs_review_true_for_stale_tier3_rule(session: Session) -> None:
    old_date = TODAY - datetime.timedelta(days=100)  # > 90 day cadence
    rule = _make_rule(session, last_verified=old_date, tier=3)
    assert needs_review(rule, [], TODAY) is True


def test_needs_review_true_when_check_stale(session: Session) -> None:
    # Rule is fresh but source-check is old
    old_date = TODAY - datetime.timedelta(days=400)
    rule = _make_rule(session, last_verified=TODAY, tier=1)
    checks = [
        SourceCheck(
            id=1,
            rule_id=rule.rule_id,
            version=rule.version,
            reference="ref-A",
            checked_at=old_date,
        )
    ]
    assert needs_review(rule, checks, TODAY) is True


def test_needs_review_true_when_url_unreachable(session: Session) -> None:
    rule = _make_rule(session, last_verified=TODAY, tier=1)
    checks = [
        SourceCheck(
            id=1,
            rule_id=rule.rule_id,
            version=rule.version,
            reference="ref-A",
            checked_at=TODAY,
            url_reachable=False,
        )
    ]
    assert needs_review(rule, checks, TODAY) is True


def test_needs_review_true_when_form_changed(session: Session) -> None:
    rule = _make_rule(session, last_verified=TODAY, tier=1)
    checks = [
        SourceCheck(
            id=1,
            rule_id=rule.rule_id,
            version=rule.version,
            reference="ref-A",
            checked_at=TODAY,
            form_changed=True,
        )
    ]
    assert needs_review(rule, checks, TODAY) is True


def test_cadence_thresholds_match_spec() -> None:
    """Verify cadence constants match analyst-sop.md §12.1."""
    assert CADENCE_DAYS[1] == 365
    assert CADENCE_DAYS[2] == 180
    assert CADENCE_DAYS[3] == 90
