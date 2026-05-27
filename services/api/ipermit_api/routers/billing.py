"""Billing endpoints (SAAS-03 / S03-01): checkout, subscription, webhook.

Checkout and subscription are tenant-scoped (authenticated). The webhook is
unauthenticated but signature-verified (HMAC) and idempotent — it is the system
path that updates subscription state, so it runs without a tenant GUC (admitted
by the subscription RLS policy). Provider failures surface as RFC-9457 problems.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from ipermit_tenancy import Subscription
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import append_audit
from ..auth import AuthenticatedIdentity, get_current_identity
from ..billing.plans import DEFAULT_PLAN, get_plan, is_valid_plan
from ..billing.provider import SignatureError, get_provider
from ..billing.service import apply_event
from ..db import apply_tenant_scope, get_session
from ..envelope import ProblemException
from ..schemas import CheckoutRequest, CheckoutResponse, SubscriptionResponse

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _require_tenant(identity: AuthenticatedIdentity) -> str:
    if identity.tenant_id is None:
        raise ProblemException(403, "No tenant membership")
    return identity.tenant_id


def _subscription_response(
    plan_key: str, status: str, period_end
) -> SubscriptionResponse:
    plan = get_plan(plan_key)
    return SubscriptionResponse(
        plan=plan.key,
        status=status,
        current_period_end=period_end,
        monthly_evaluations=plan.monthly_evaluations,
        monthly_exports=plan.monthly_exports,
    )


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> SubscriptionResponse:
    """Return the caller tenant's subscription (default free if none)."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    sub = session.scalar(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    )
    if sub is None:
        return _subscription_response(DEFAULT_PLAN, "active", None)
    return _subscription_response(sub.plan, sub.status, sub.current_period_end)


@router.post("/checkout", response_model=CheckoutResponse)
def start_checkout(
    body: CheckoutRequest,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> CheckoutResponse:
    """Begin a hosted checkout for a plan (consultant/tenant)."""
    tenant_id = _require_tenant(identity)
    if not is_valid_plan(body.plan):
        raise ProblemException(422, f"Unknown plan {body.plan!r}")
    apply_tenant_scope(session, tenant_id)
    url = get_provider().create_checkout(tenant_id=tenant_id, plan=body.plan)
    append_audit(
        session,
        actor=identity.email,
        action="billing.checkout_started",
        subject=tenant_id,
        payload={"plan": body.plan},
    )
    session.commit()
    return CheckoutResponse(checkout_url=url)


@router.post("/webhook")
async def billing_webhook(
    request: Request, session: Session = Depends(get_session)
) -> dict[str, str]:
    """Apply a signature-verified, idempotent subscription webhook (system path)."""
    payload = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    try:
        event = get_provider().parse_event(payload, signature)
    except SignatureError as exc:
        raise ProblemException(400, "Invalid webhook signature") from exc
    except (KeyError, ValueError) as exc:
        raise ProblemException(400, "Malformed webhook payload") from exc
    subscription = apply_event(session, event)
    if subscription is None:
        return {"status": "duplicate"}  # replay — already processed
    append_audit(
        session,
        actor="system:billing",
        action="billing.subscription_updated",
        subject=event.tenant_id,
        payload={
            "plan": event.plan,
            "status": event.status,
            "event_id": event.event_id,
        },
    )
    session.commit()
    return {"status": "ok"}
