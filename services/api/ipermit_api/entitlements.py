"""Entitlement gating dependency (S03-02, SAAS-03).

Provides ``require_entitlement(*plans)`` — a FastAPI dependency factory that
reads the caller's ``TenantBilling`` row and raises a RFC-9457 402/403 problem
if the tenant does not hold an *active* qualifying plan.

Design invariants:
- **Composes with RBAC** — callers chain ``require_role`` (or
  ``get_current_identity``) alongside ``require_entitlement``; this module never
  duplicates auth/role logic.
- **Active = status 'active' AND not past current_period_end** — a canceled,
  past-due, or expired row is not entitled, even if the plan column says so.
- **Free plan is never entitled for premium routes** — only plans in the
  ``plans`` tuple passed to the factory.
- **402 Payment Required** is returned when the tenant exists but the plan is
  not qualifying.  ``403 Forbidden`` is returned when the identity has no
  tenant at all (no membership).
- **No new queries** — re-uses ``billing_core.get_billing`` so no extra DB
  seam is needed.

``PLAN_CATALOG`` is the server-side authoritative list of plans and what each
unlocks.  The ``GET /api/v1/billing/plans`` route serves it to the frontend so
the pricing page never hard-codes plan metadata.
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import Depends
from ipermit_tenancy import TenantBilling
from sqlalchemy.orm import Session

from . import billing as billing_core
from .auth import AuthenticatedIdentity, get_current_identity
from .db import apply_tenant_scope, get_session
from .envelope import ProblemException

#: Server-side plan catalog — single source of truth for the pricing surface.
#: ``plans`` lists which paid plans include this tier's features.
PLAN_CATALOG: list[dict[str, Any]] = [
    {
        "plan": "free",
        "display_name": "Free",
        "description": "Get started with basic permit evaluation.",
        "price_monthly_usd": None,
        "features": [
            "Unlimited projects",
            "Permit matrix evaluation",
            "Evaluation history",
            "Feedback submission",
        ],
        "premium": False,
    },
    {
        "plan": "starter",
        "display_name": "Starter",
        "description": "For individual consultants needing deliverables.",
        "price_monthly_usd": "29",
        "features": [
            "Everything in Free",
            "Export permit matrix (JSON, XLSX, PDF)",
            "Priority support",
        ],
        "premium": True,
    },
    {
        "plan": "pro",
        "display_name": "Pro",
        "description": "For teams with advanced workflow needs.",
        "price_monthly_usd": "99",
        "features": [
            "Everything in Starter",
            "Team collaboration",
            "Advanced analytics",
            "Dedicated support",
        ],
        "premium": True,
    },
]


def _is_active(billing: TenantBilling) -> bool:
    """True iff billing status is 'active' and not past the current_period_end.

    SQLite stores datetimes as naive strings; PostgreSQL stores them with tz.
    We normalise both to UTC-aware before comparison.
    """
    if billing.status != "active":
        return False
    if billing.current_period_end is None:
        return True
    period_end = billing.current_period_end
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=datetime.UTC)
    now = datetime.datetime.now(tz=datetime.UTC)
    return now < period_end


def _check_entitlement(
    identity: AuthenticatedIdentity,
    session: Session,
    plans: tuple[str, ...],
) -> AuthenticatedIdentity:
    """Raise 402/403 if the tenant is not entitled to one of *plans*."""
    tenant_id = identity.tenant_id
    if tenant_id is None:
        raise ProblemException(403, "No tenant membership")
    apply_tenant_scope(session, tenant_id)
    billing = billing_core.get_billing(session, tenant_id)
    if billing is None or not _is_active(billing) or billing.plan not in plans:
        raise ProblemException(
            402,
            "Subscription required",
            f"This feature requires an active plan in: {', '.join(plans)}.",
            type_="urn:ipermit:billing:subscription-required",
        )
    return identity


def require_entitlement(*plans: str):
    """Dependency factory: gate a route to callers with an active plan in *plans*.

    Compose with auth:
        Depends(require_entitlement("starter", "pro"))

    The dependency also resolves ``get_current_identity`` so routes that use
    ``require_entitlement`` do not need to separately depend on
    ``get_current_identity``; they receive the ``AuthenticatedIdentity`` return.

    Raises:
        403 — if the caller has no tenant membership.
        402 — if the tenant has no active qualifying plan.
    """

    def dependency(
        identity: AuthenticatedIdentity = Depends(get_current_identity),
        session: Session = Depends(get_session),
    ) -> AuthenticatedIdentity:
        return _check_entitlement(identity, session, plans)

    return dependency
