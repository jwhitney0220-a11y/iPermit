"""QA/QC dashboard surface (S05-03, roadmap T04-05 web).

Computes a rule-health snapshot from the on-disk rule store and exposes it for
the analyst portal. Counts by status and confidence tier, the freshness window
(rules whose provenance ``last_verified`` is older than the threshold), and
totals — read-only, on demand, no DB writes.
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends
from ipermit_rules import load_rules
from pydantic import BaseModel

from ..auth import AuthenticatedIdentity, require_role

router = APIRouter(prefix="/api/v1/qa", tags=["qa"])

#: Days after which a rule's ``last_verified`` is considered stale (engine default).
_STALE_THRESHOLD_DAYS = 365


class StaleRule(BaseModel):
    rule_id: str
    rule_version: str
    status: str
    last_verified: str | None
    days_since_verified: int | None


class QaReportResponse(BaseModel):
    """Rule-health snapshot for the analyst QA/QC dashboard."""

    generated_at: datetime.datetime
    total_rules: int
    by_status: dict[str, int]
    by_tier: dict[str, int]
    stale_rules: list[StaleRule]


def _days_since(last_verified: str | None, today: datetime.date) -> int | None:
    if not last_verified:
        return None
    try:
        return max(0, (today - datetime.date.fromisoformat(last_verified)).days)
    except ValueError:
        return None


def _stale_rule(rule: Any, today: datetime.date) -> StaleRule | None:
    last = rule.data.get("provenance", {}).get("last_verified")
    days = _days_since(last, today)
    if days is None or days <= _STALE_THRESHOLD_DAYS:
        return None
    return StaleRule(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        status=rule.status,
        last_verified=last,
        days_since_verified=days,
    )


@router.get("/report", response_model=QaReportResponse)
def qa_report(
    _identity: AuthenticatedIdentity = Depends(require_role("regulatory_analyst")),
) -> QaReportResponse:
    """Return the current rule-health snapshot (analyst-only)."""
    rules = load_rules()
    today = datetime.date.today()
    by_status: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    stale: list[StaleRule] = []
    for rule in rules:
        by_status[rule.status] = by_status.get(rule.status, 0) + 1
        tier = str(rule.data.get("confidence_tier", "?"))
        by_tier[tier] = by_tier.get(tier, 0) + 1
        item = _stale_rule(rule, today)
        if item is not None:
            stale.append(item)
    stale.sort(key=lambda r: (-(r.days_since_verified or 0), r.rule_id))
    return QaReportResponse(
        generated_at=datetime.datetime.now(tz=datetime.UTC),
        total_rules=len(rules),
        by_status=by_status,
        by_tier=by_tier,
        stale_rules=stale,
    )
