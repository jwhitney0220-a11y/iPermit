"""Temporal rule activation logic for the iPermit rules engine (T02-04).

Implements the selection algorithm from docs/specs/temporal-versioning.md §4.
The three public functions mirror the three concepts callers need:

- ``is_governing``     — pure predicate on a single rule object (no DB)
- ``effective_rule``   — picks the governing version of one rule_id on a date
- ``effective_ruleset`` — picks the governing version of every rule_id on a date

Boundary semantics (``effective_to`` inclusive):
    The spec §4 candidate filter is:
        effective_from <= D AND (effective_to is unset OR effective_to >= D)
    Both endpoints are **inclusive**.  This matches the worked example in §4.2:
    Project C submitted on 2025-12-31 matches v1.0.0 (effective_to=2025-12-31)
    AND v2.0.0 (effective_from=2025-12-31), so both are candidates and the
    tie-break (latest effective_from) selects v2.0.0.  If effective_to were
    exclusive, v1.0.0 would not be a candidate that day, making the tie-break
    example moot — contradicting the spec's intent.

Governing statuses:
    Only ``effective`` and ``archived`` rules participate in selection (§4).
    ``draft`` and ``published`` rules are never returned, even if their date
    windows match, because a published-but-not-yet-effective rule must not fire
    (AGENTS.md Temporal Versioning; spec §3.1).

Determinism:
    When multiple versions have the same latest ``effective_from``, the spec
    says to pick by highest semver ``version``.  Because semver comparison
    requires a dependency, we use Python's ``tuple(int, …)`` parsing for
    well-formed semver strings and fall back to lexicographic order, which is
    sufficient for the analyst SOP that prevents true ties (spec §4 tie-break).
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import RegulatoryRule

# Statuses that may govern an evaluation date (spec §4, Table §3).
_GOVERNING_STATUSES = frozenset({"effective", "archived"})


def is_governing(rule: RegulatoryRule, on_date: datetime.date) -> bool:
    """Return True if *rule* governs evaluations on *on_date*.

    Pure function — no database access.  Implements the per-rule predicate
    from spec §4:
        status in {effective, archived}
        AND effective_from is not null AND effective_from <= on_date
        AND (effective_to is null OR effective_to >= on_date)

    Both ``effective_from`` and ``effective_to`` are inclusive (see module
    docstring for rationale).
    """
    if rule.status not in _GOVERNING_STATUSES:
        return False
    if rule.effective_from is None:
        return False
    if rule.effective_from > on_date:
        return False
    return rule.effective_to is None or rule.effective_to >= on_date


def _semver_key(version: str) -> tuple[int | str, ...]:
    """Return a sort key for a version string.

    Parses ``MAJOR.MINOR.PATCH`` into a tuple of ints for well-formed semver;
    falls back to a single-element tuple of the raw string so that any version
    is sortable.  Higher tuples sort later, so ``max(versions, key=…)`` returns
    the highest version.
    """
    parts = version.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return (version,)


def _best(candidates: Sequence[RegulatoryRule]) -> RegulatoryRule:
    """Pick the governing rule from a non-empty sequence of candidates.

    Tie-breaking per spec §4:
      1. Latest ``effective_from`` (most-recent activation date).
      2. Highest semver ``version``.
      3. If still tied, the spec calls it an SOP violation; we raise to surface
         the data-quality problem rather than make an arbitrary choice.
    """
    latest_from = max(r.effective_from for r in candidates)  # type: ignore[arg-type]
    after_step1 = [r for r in candidates if r.effective_from == latest_from]
    if len(after_step1) == 1:
        return after_step1[0]

    best_ver = max(_semver_key(r.version) for r in after_step1)
    after_step2 = [r for r in after_step1 if _semver_key(r.version) == best_ver]
    if len(after_step2) == 1:
        return after_step2[0]

    ids = ", ".join(f"{r.rule_id}@{r.version}" for r in after_step2)
    raise ValueError(
        f"SOP violation: multiple rule versions cannot be disambiguated: {ids}"
    )


def effective_rule(
    session: Session,
    rule_id: str,
    on_date: datetime.date,
) -> RegulatoryRule | None:
    """Return the governing version of *rule_id* on *on_date*, or None.

    Queries the ``regulatory_rule`` table for all versions of *rule_id* whose
    status and date window make them candidates per spec §4, then applies the
    deterministic tie-break.  Returns ``None`` when no version governs that
    date (e.g. the rule did not exist yet, or every version has expired).

    Replay semantics: passing a past ``on_date`` returns the version that would
    have been selected on that date — archived rules are included so that
    historical evaluations remain reproducible regardless of when the query is
    run (spec §6).
    """
    stmt = select(RegulatoryRule).where(
        RegulatoryRule.rule_id == rule_id,
        RegulatoryRule.status.in_(list(_GOVERNING_STATUSES)),
        RegulatoryRule.effective_from.isnot(None),
        RegulatoryRule.effective_from <= on_date,
    )
    rows = session.scalars(stmt).all()
    candidates = [r for r in rows if is_governing(r, on_date)]
    if not candidates:
        return None
    return _best(candidates)


def effective_ruleset(
    session: Session,
    on_date: datetime.date,
) -> list[RegulatoryRule]:
    """Return the governing rule for every rule_id that has one on *on_date*.

    Queries all candidate rows in one pass, groups them by ``rule_id``, and
    applies ``_best`` per group.  Rules for which no version governs *on_date*
    (e.g. draft-only rules, future rules) are silently omitted — callers that
    need to detect absent rules should query separately.

    The returned list is sorted by ``rule_id`` for determinism.
    """
    stmt = select(RegulatoryRule).where(
        RegulatoryRule.status.in_(list(_GOVERNING_STATUSES)),
        RegulatoryRule.effective_from.isnot(None),
        RegulatoryRule.effective_from <= on_date,
    )
    rows = session.scalars(stmt).all()

    by_id: dict[str, list[RegulatoryRule]] = {}
    for row in rows:
        if is_governing(row, on_date):
            by_id.setdefault(row.rule_id, []).append(row)

    result: list[RegulatoryRule] = []
    for rule_id in sorted(by_id):
        result.append(_best(by_id[rule_id]))
    return result
