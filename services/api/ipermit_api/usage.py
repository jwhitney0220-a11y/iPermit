"""Per-tenant usage metering (S03-03, SAAS-03).

Append-only event log: one ``UsageRecord`` row per billable action. Aggregation
(counts per metric) is done on read with a single GROUP-BY query.

Design choice — event log vs. per-period counter:
  Event log was chosen because every billable event is individually auditable
  (dispute resolution without history reconstruction), the write path is a
  trivial single INSERT with no period-management logic, and ad-hoc period
  windows (monthly, rolling-30-day, Stripe billing cycle) map to one SQL
  WHERE + GROUP-BY against the raw events.

Usage records are tenant-scoped at the application layer (explicit tenant_id
filter on every read) and at the database layer via Postgres RLS (ADR-0002).
``apply_tenant_scope`` is called by callers that own the session transaction;
this module requires the scope already set and always filters by tenant_id.
"""

from __future__ import annotations

import datetime

from ipermit_tenancy import UsageRecord
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def record_usage(
    session: Session,
    *,
    tenant_id: str,
    metric: str,
    quantity: int = 1,
) -> UsageRecord:
    """Append one usage event for *tenant_id* and return it (flushed, not committed).

    The caller owns the transaction. ``session.flush()`` makes the row visible
    within the transaction so the caller can read it back before committing.
    Intentionally kept minimal — no entitlement check, no side effects beyond
    the INSERT — so it composes cleanly into any transactional boundary.
    """
    record = UsageRecord(
        tenant_id=tenant_id,
        metric=metric,
        quantity=quantity,
        occurred_at=datetime.datetime.now(tz=datetime.UTC),
    )
    session.add(record)
    session.flush()
    return record


def get_period_summary(
    session: Session,
    *,
    tenant_id: str,
    period_start: datetime.datetime,
    period_end: datetime.datetime,
) -> dict[str, int]:
    """Return {metric: total_quantity} for *tenant_id* in [period_start, period_end).

    Filters strictly by tenant_id so a caller can never see another tenant's
    data even if the Postgres RLS GUC is not set (two-layer defence, ADR-0002).
    """
    rows = session.execute(
        select(UsageRecord.metric, func.sum(UsageRecord.quantity).label("total"))
        .where(
            UsageRecord.tenant_id == tenant_id,
            UsageRecord.occurred_at >= period_start,
            UsageRecord.occurred_at < period_end,
        )
        .group_by(UsageRecord.metric)
    ).all()
    return {row.metric: int(row.total) for row in rows}


def report_usage_to_stripe(
    tenant_id: str,
    metric: str,
    quantity: int,
    period_start: datetime.datetime,
) -> None:
    """Stub: report aggregated usage to Stripe metered billing (wired later).

    When iPermit moves to Stripe metered prices (usage-based billing), this
    function will call ``stripe.SubscriptionItems.create_usage_record`` with
    the tenant's subscription item id and the aggregated quantity for the
    period. The stub is intentionally a no-op so the call site in a future
    billing-cycle job can be wired without touching the metering logic.

    Args:
        tenant_id: The tenant whose usage is being reported.
        metric: The metric name (e.g. ``"evaluation"``).
        quantity: Aggregated count for the billing period.
        period_start: Unix-epoch start of the billing period (Stripe timestamp).

    Wired-later: S03-05 (metered price reporting) will fill this in once the
    Stripe subscription item id is stored on ``TenantBilling`` and a periodic
    job (Celery/Cloud Scheduler) drives the nightly/monthly reconciliation.
    """
