"""Source-link / citation health surface (S05-04, roadmap T08-03 / T08-05).

Flattens every citation across the rule store with a per-citation **health**
classification. Complements the rule-level snapshot (S05-03) with the
citation-level view analysts use to spot broken or stale source links — the
"rule health & source-expiration monitoring" the analyst portal needs.

Read-only and computed on demand. The HTTP-probe side of source verification
(reachability + content drift) lives in ``ipermit_regulatory.sources`` and is
populated by a separate verification job (out of scope); this endpoint surfaces
what is knowable from the rule files alone, which is the most common analyst
question and needs no external requests.
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends
from ipermit_rules import load_rules
from pydantic import BaseModel

from ..auth import AuthenticatedIdentity, require_role

router = APIRouter(prefix="/api/v1/qa", tags=["qa"])

_STALE_THRESHOLD_DAYS = 365


class CitationHealth(BaseModel):
    rule_id: str
    rule_version: str
    rule_status: str
    citation_type: str
    reference: str
    url: str | None
    rule_last_verified: str | None
    days_since_verified: int | None
    health: str  # "ok" | "stale" | "missing_url"


class SourcesReport(BaseModel):
    """Citation-level health snapshot for the analyst portal."""

    generated_at: datetime.datetime
    total_citations: int
    health_counts: dict[str, int]
    citations: list[CitationHealth]


def _days_since(last_verified: str | None, today: datetime.date) -> int | None:
    if not last_verified:
        return None
    try:
        return max(0, (today - datetime.date.fromisoformat(last_verified)).days)
    except ValueError:
        return None


def _health(citation: dict[str, Any], days: int | None) -> str:
    if not citation.get("url"):
        return "missing_url"
    if days is not None and days > _STALE_THRESHOLD_DAYS:
        return "stale"
    return "ok"


def _citation_item(
    rule: Any, citation: dict[str, Any], today: datetime.date
) -> CitationHealth:
    last = rule.data.get("provenance", {}).get("last_verified")
    days = _days_since(last, today)
    return CitationHealth(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        rule_status=rule.status,
        citation_type=citation.get("citation_type", "unknown"),
        reference=citation["reference"],
        url=citation.get("url"),
        rule_last_verified=last,
        days_since_verified=days,
        health=_health(citation, days),
    )


def _sort_key(item: CitationHealth) -> tuple[int, int, str]:
    """Sort: missing_url and stale first, then by most-stale days, then rule_id."""
    rank = {"missing_url": 0, "stale": 1, "ok": 2}[item.health]
    return (rank, -(item.days_since_verified or 0), item.rule_id)


@router.get("/sources", response_model=SourcesReport)
def sources_report(
    _identity: AuthenticatedIdentity = Depends(require_role("regulatory_analyst")),
) -> SourcesReport:
    """Return a citation-level health snapshot across all rules (analyst-only)."""
    rules = load_rules()
    today = datetime.date.today()
    items: list[CitationHealth] = []
    for rule in rules:
        for citation in rule.data.get("provenance", {}).get("source_citations", []):
            items.append(_citation_item(rule, citation, today))
    items.sort(key=_sort_key)
    counts: dict[str, int] = {}
    for item in items:
        counts[item.health] = counts.get(item.health, 0) + 1
    return SourcesReport(
        generated_at=datetime.datetime.now(tz=datetime.UTC),
        total_citations=len(items),
        health_counts=counts,
        citations=items,
    )
