"""Billing endpoints: checkout, signature-verified webhook, entitlement read.

S03-01 (SAAS-03). Security invariants (run security-review on changes here):

- ``POST /billing/checkout`` is auth-gated and creates a Stripe Checkout Session
  from a SERVER-SIDE Price ID resolved by plan name — never a client amount.
- ``POST /billing/webhook`` is UNAUTH'd (Stripe calls it) but every event is
  signature-verified via ``construct_event`` before it is trusted; an unverified
  body is rejected with an RFC-9457 problem and changes no state.
- Entitlement (plan/status on ``TenantBilling``) is written ONLY from verified
  webhook events — never from the checkout request or its browser redirect.
- Idempotent: each Stripe ``event.id`` is recorded once; a redelivery is a no-op.
- ``GET /billing`` is a read-only view of the caller's tenant entitlement (no
  gating enforcement yet — that is S03-02).
"""

from __future__ import annotations

from typing import Any

import stripe
from fastapi import APIRouter, Depends, Request
from ipermit_tenancy import ProcessedStripeEvent, TenantBilling
from sqlalchemy.orm import Session

from .. import billing as billing_core
from ..audit import append_audit
from ..auth import AuthenticatedIdentity, get_current_identity
from ..db import apply_tenant_scope, get_session
from ..envelope import ProblemException
from ..schemas import (
    BillingResponse,
    CheckoutRequest,
    CheckoutResponse,
)
from ..settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

#: Stripe events this webhook handles. Unhandled types are acknowledged (200)
#: and recorded for idempotency so Stripe stops retrying, but mutate nothing.
_HANDLED = (
    "checkout.session.completed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
)


def _require_tenant(identity: AuthenticatedIdentity) -> str:
    """Return the caller's active tenant, or raise 403 if they have none."""
    if identity.tenant_id is None:
        raise ProblemException(403, "No tenant membership")
    return identity.tenant_id


@router.get("", response_model=BillingResponse)
def get_my_billing(
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> BillingResponse:
    """Return the caller's tenant plan/status (read-only; no gating yet)."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    billing = billing_core.get_billing(session, tenant_id)
    return BillingResponse(
        tenant_id=tenant_id,
        plan=billing.plan if billing else "free",
        status=billing.status if billing else "none",
        current_period_end=billing.current_period_end if billing else None,
    )


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    body: CheckoutRequest,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> CheckoutResponse:
    """Create a Stripe Checkout Session for a paid plan (auth-gated).

    Resolves the plan to a server-side Price ID and ensures the tenant's Stripe
    customer exists. Entitlement is NOT changed here — only the later verified
    webhook grants the plan.
    """
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    billing = billing_core.ensure_customer(
        session, settings, tenant_id=tenant_id, email=identity.email
    )
    checkout = billing_core.create_checkout_session(
        settings,
        customer_id=billing.stripe_customer_id,
        plan=body.plan,
        tenant_id=tenant_id,
    )
    append_audit(
        session,
        actor=identity.email,
        action="billing.checkout_started",
        subject=tenant_id,
        payload={"plan": body.plan, "checkout_session_id": checkout.id},
    )
    session.commit()
    return CheckoutResponse(checkout_url=checkout.url)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Receive a Stripe webhook: verify -> dedupe -> apply entitlement -> ack.

    Unauth'd (Stripe calls it). The signature is verified before the body is
    trusted; an unverified body is a 400 problem and mutates nothing.
    """
    event = await _verify_event(request, settings)
    if _already_processed(session, event["id"]):
        return {"status": "duplicate"}
    if event["type"] in _HANDLED:
        _dispatch(session, event)
    _record_event(session, event)
    session.commit()
    return {"status": "ok"}


async def _verify_event(request: Request, settings: Settings) -> Any:
    """Verify the Stripe-Signature header, or raise a 400 RFC-9457 problem."""
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    try:
        return billing_core.construct_event(settings, payload, signature)
    except (stripe.SignatureVerificationError, ValueError) as exc:
        raise ProblemException(400, "Invalid Stripe signature") from exc


def _already_processed(session: Session, event_id: str) -> bool:
    """True if this Stripe event id was already handled (idempotency)."""
    return session.get(ProcessedStripeEvent, event_id) is not None


def _record_event(session: Session, event: Any) -> None:
    """Append the event id to the idempotency ledger (flushed, not committed)."""
    session.add(ProcessedStripeEvent(event_id=event["id"], event_type=event["type"]))
    session.flush()


def _dispatch(session: Session, event: Any) -> None:
    """Route a handled, verified event to its entitlement updater + audit."""
    obj = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        _on_checkout_completed(session, obj)
    else:
        _on_subscription_change(session, event["type"], obj)


def _field(obj: Any, key: str, default: Any = None) -> Any:
    """Read *key* from a Stripe ``StripeObject`` or plain dict.

    ``StripeObject`` supports ``in`` and ``[]`` but shadows ``.get`` via its
    attribute proxy, so we cannot call ``obj.get(...)`` on a verified event
    (hence the explicit membership test, not ``dict.get``).
    """
    return obj[key] if key in obj else default  # noqa: SIM401


def _tenant_from_metadata(obj: Any) -> str | None:
    """Read the tenant id stamped into Stripe object metadata, or None."""
    metadata = _field(obj, "metadata") or {}
    return _field(metadata, "tenant_id")


def _upsert_billing(session: Session, tenant_id: str) -> TenantBilling:
    """Load (RLS-scoped) or create the tenant's billing row."""
    apply_tenant_scope(session, tenant_id)
    billing = billing_core.get_billing(session, tenant_id)
    if billing is None:
        billing = TenantBilling(tenant_id=tenant_id)
        session.add(billing)
    return billing


def _on_checkout_completed(session: Session, obj: Any) -> None:
    """Grant the purchased plan on a completed checkout (active entitlement)."""
    tenant_id = _tenant_from_metadata(obj)
    if tenant_id is None:
        return
    billing = _upsert_billing(session, tenant_id)
    billing.plan = _field(_field(obj, "metadata") or {}, "plan", billing.plan)
    billing.status = "active"
    billing.stripe_subscription_id = _field(obj, "subscription")
    if _field(obj, "customer"):
        billing.stripe_customer_id = _field(obj, "customer")
    session.flush()
    _audit_billing(session, "billing.subscription_activated", billing)


def _on_subscription_change(session: Session, event_type: str, obj: Any) -> None:
    """Apply a subscription update/deletion to the tenant's entitlement."""
    tenant_id = _tenant_from_metadata(obj)
    if tenant_id is None:
        return
    billing = _upsert_billing(session, tenant_id)
    billing.stripe_subscription_id = _field(obj, "id")
    plan = _field(_field(obj, "metadata") or {}, "plan")
    if plan:
        billing.plan = plan
    if event_type == "customer.subscription.deleted":
        billing.status = "canceled"
    else:
        billing.status = billing_core.map_status(_field(obj, "status"))
    billing.current_period_end = billing_core.period_end(
        _field(obj, "current_period_end")
    )
    session.flush()
    _audit_billing(session, f"billing.{event_type}", billing)


def _audit_billing(session: Session, action: str, billing: TenantBilling) -> None:
    """Write one audit record for a billing entitlement change (ADR-0004)."""
    append_audit(
        session,
        actor="stripe.webhook",
        action=action,
        subject=billing.tenant_id,
        payload={
            "tenant_id": billing.tenant_id,
            "plan": billing.plan,
            "status": billing.status,
            "stripe_subscription_id": billing.stripe_subscription_id,
        },
    )
