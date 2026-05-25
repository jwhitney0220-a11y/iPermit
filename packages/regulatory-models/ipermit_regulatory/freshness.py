"""Data freshness scoring for regulatory rules (T02-07).

Computes a freshness score that is INDEPENDENT of confidence tier. A Tier-1
rule (fully verified, statutory) can still be *stale* if it has not been
re-verified within its cadence window. Freshness is a time-and-reachability
dimension; confidence is a source-quality dimension.

Score scale: 0 (worst) - 100 (best).
  90-100  fresh     -- checked recently, all sources reachable, no form changes
  50-89   aging     -- approaching the cadence threshold or minor signals
  0-49    stale     -- past cadence threshold, unreachable URL, or form changed

Default re-verification cadences (analyst-SOP ss12.1):
  Tier 1  365 days
  Tier 2  180 days
  Tier 3   90 days

These are upper bounds. Any tier's rule flags as stale once past its cadence,
regardless of how high the confidence tier is.
"""

from __future__ import annotations

import datetime
from enum import StrEnum

from .models import RegulatoryRule, SourceCheck

# ---------------------------------------------------------------------------
# Cadence thresholds in days -- kept in one place for easy policy updates.
# ---------------------------------------------------------------------------

CADENCE_DAYS: dict[int, int] = {1: 365, 2: 180, 3: 90}
_DEFAULT_CADENCE = 90  # applied when confidence_tier is out of range

# Score thresholds that separate fresh / aging / stale.
_FRESH_THRESHOLD = 90
_AGING_THRESHOLD = 50


class FreshnessLabel(StrEnum):
    """Human-readable freshness label derived from the numeric score."""

    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"


def _cadence(tier: int) -> int:
    """Return the review cadence (days) for a confidence tier."""
    return CADENCE_DAYS.get(tier, _DEFAULT_CADENCE)


def _days_since(date: datetime.date, today: datetime.date) -> int:
    """Return the number of calendar days between *date* and *today*."""
    return (today - date).days


def _url_penalty(checks: list[SourceCheck]) -> int:
    """Return a score penalty for unreachable URLs or form changes.

    Examines the most-recent check per unique reference. Deducts 30 points for
    each unreachable URL and 20 points for each detected form change, capped at
    50 total so a single bad citation does not zero out the score.
    """
    latest: dict[str, SourceCheck] = {}
    for check in checks:
        prev = latest.get(check.reference)
        if prev is None or (check.checked_at, check.id) > (prev.checked_at, prev.id):
            latest[check.reference] = check

    penalty = 0
    for check in latest.values():
        if check.url_reachable is False:
            penalty += 30
        if check.form_changed is True:
            penalty += 20
    return min(penalty, 50)


def _last_check_date(checks: list[SourceCheck]) -> datetime.date | None:
    """Return the most recent ``checked_at`` date across all checks, or None."""
    if not checks:
        return None
    return max(c.checked_at for c in checks)


def freshness_score(
    rule: RegulatoryRule,
    checks: list[SourceCheck],
    today: datetime.date,
) -> int:
    """Compute a freshness score (0-100) for a rule.

    Inputs
    ------
    rule    : The RegulatoryRule whose ``last_verified`` and ``confidence_tier``
              drive the cadence calculation.
    checks  : All SourceCheck rows for this (rule_id, version). May be empty.
    today   : The reference date (pass ``datetime.date.today()`` in production;
              inject in tests for determinism).

    Score composition
    -----------------
    Base score (0-100) decays linearly from 100 at zero days old to 0 when
    days_since_verified equals the cadence. A second decay term uses the most
    recent source check (if any) against the same cadence. The lower of the two
    base scores is used, then the URL/form-change penalty is subtracted.

    Note: freshness is orthogonal to confidence_tier. A Tier-1 rule that has
    not been re-verified in 400 days scores poorly here.
    """
    cadence = _cadence(rule.confidence_tier)

    days_rule = _days_since(rule.last_verified, today)
    base_rule = max(0, 100 - int(100 * days_rule / cadence))

    last_check = _last_check_date(checks)
    if last_check is not None:
        days_check = _days_since(last_check, today)
        base_check = max(0, 100 - int(100 * days_check / cadence))
        base = min(base_rule, base_check)
    else:
        base = base_rule

    penalty = _url_penalty(checks)
    return max(0, base - penalty)


def freshness_label(score: int) -> FreshnessLabel:
    """Convert a numeric score into a ``FreshnessLabel``.

    Thresholds: 90-100 -> fresh, 50-89 -> aging, 0-49 -> stale.
    """
    if score >= _FRESH_THRESHOLD:
        return FreshnessLabel.FRESH
    if score >= _AGING_THRESHOLD:
        return FreshnessLabel.AGING
    return FreshnessLabel.STALE


def needs_review(
    rule: RegulatoryRule,
    checks: list[SourceCheck],
    today: datetime.date,
) -> bool:
    """Return True if the rule requires analyst re-verification.

    Triggers when ANY of the following is true:
    - Days since ``last_verified`` exceeds the tier cadence threshold.
    - Days since the latest source check exceeds the tier cadence threshold.
    - The most-recent check for any reference shows ``url_reachable=False``.
    - The most-recent check for any reference shows ``form_changed=True``.

    This predicate is independent of confidence tier: a stale Tier-1 rule
    (e.g. last verified 400 days ago when the cadence is 365) returns True.
    """
    cadence = _cadence(rule.confidence_tier)

    if _days_since(rule.last_verified, today) > cadence:
        return True

    last_check = _last_check_date(checks)
    if last_check is not None and _days_since(last_check, today) > cadence:
        return True

    latest: dict[str, SourceCheck] = {}
    for check in checks:
        prev = latest.get(check.reference)
        if prev is None or (check.checked_at, check.id) > (prev.checked_at, prev.id):
            latest[check.reference] = check

    for check in latest.values():
        if check.url_reachable is False:
            return True
        if check.form_changed is True:
            return True

    return False
