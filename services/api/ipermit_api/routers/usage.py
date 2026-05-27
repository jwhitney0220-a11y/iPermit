"""Usage metering endpoint (S03-03): GET /api/v1/usage.

Returns the caller tenant's current-period usage summary (counts per metric).
Auth-gated: requires a valid bearer token and an active tenant membership.
The period defaults to the current calendar month (UTC); callers may supply
an explicit ``period_start`` ISO-8601 date to query a different month.
"""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import AuthenticatedIdentity, get_current_identity
from ..db import apply_tenant_scope, get_session
from ..envelope import ProblemException
from ..usage import get_period_summary

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])

_DECEMBER = 12


class UsageSummary(BaseModel):
    """Per-tenant usage counts for the requested billing period."""

    tenant_id: str
    period_start: str
    period_end: str
    metrics: dict[str, int]


def _require_tenant(identity: AuthenticatedIdentity) -> str:
    """Return the caller's active tenant, or raise 403 if they have none."""
    if identity.tenant_id is None:
        raise ProblemException(403, "No tenant membership")
    return identity.tenant_id


def _current_period() -> tuple[datetime.datetime, datetime.datetime]:
    """Return [start, end) for the current calendar month in UTC."""
    now = datetime.datetime.now(tz=datetime.UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == _DECEMBER:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _parse_period_start(period_start: str | None) -> datetime.datetime:
    """Parse an optional ISO date into a UTC midnight datetime."""
    if period_start is None:
        return _current_period()[0]
    try:
        d = datetime.date.fromisoformat(period_start)
    except ValueError as exc:
        raise ProblemException(
            422, "Invalid period_start", "Expected an ISO-8601 date (YYYY-MM-DD)."
        ) from exc
    return datetime.datetime(d.year, d.month, 1, tzinfo=datetime.UTC)


@router.get("", response_model=UsageSummary)
def get_usage(
    period_start: Annotated[str | None, Query()] = None,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> UsageSummary:
    """Return the caller tenant's usage summary for the given (or current) period.

    ``period_start`` is an optional ISO-8601 date (YYYY-MM-DD); the period
    covers the full calendar month containing that date. Omit for the current
    month. The response is tenant-scoped: a caller can only see their own
    tenant's counts.
    """
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    p_start = _parse_period_start(period_start)
    _, p_end = _current_period() if period_start is None else (None, None)
    if period_start is not None:
        if p_start.month == _DECEMBER:
            p_end = p_start.replace(year=p_start.year + 1, month=1)
        else:
            p_end = p_start.replace(month=p_start.month + 1)
    metrics = get_period_summary(
        session, tenant_id=tenant_id, period_start=p_start, period_end=p_end
    )
    return UsageSummary(
        tenant_id=tenant_id,
        period_start=p_start.date().isoformat(),
        period_end=p_end.date().isoformat(),
        metrics=metrics,
    )
