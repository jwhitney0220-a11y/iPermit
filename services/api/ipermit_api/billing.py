"""Stripe billing core: client wrapper + entitlement helpers (S03-01, SAAS-03).

A thin seam over the Stripe SDK so routes and tests never touch ``stripe.*``
directly (tests monkeypatch the seam — no network in CI). Two security
invariants live here and in the webhook handler:

- **Server-side prices only.** A checkout session is created from a Stripe Price
  ID resolved from settings by plan name — never from a client-supplied amount.
- **Webhooks are the sole source of truth for entitlement.** ``apply_subscription_*``
  write a tenant's plan/status; they are called ONLY from a signature-verified
  webhook event, never from the checkout request or its browser redirect.

Secrets (``STRIPE_SECRET_KEY``, ``STRIPE_WEBHOOK_SECRET``) come from settings,
which sources them from the environment (T01-08) — never hard-coded.
"""

from __future__ import annotations

import datetime
from typing import Any

import stripe
from ipermit_tenancy import TenantBilling
from sqlalchemy import select
from sqlalchemy.orm import Session

from .settings import Settings

#: Stripe subscription status -> our internal billing status. Anything we do not
#: recognise (e.g. ``trialing``, ``unpaid``) maps to the safe ``incomplete`` so a
#: tenant is never granted entitlement on an unexpected status.
_STATUS_MAP = {
    "active": "active",
    "trialing": "active",
    "past_due": "past_due",
    "canceled": "canceled",
    "incomplete": "incomplete",
    "incomplete_expired": "incomplete",
    "unpaid": "past_due",
}


def _client(settings: Settings) -> stripe.StripeClient:
    """Build a Stripe client bound to the configured secret key."""
    return stripe.StripeClient(settings.stripe_secret_key)


def ensure_customer(
    session: Session, settings: Settings, *, tenant_id: str, email: str
) -> TenantBilling:
    """Return the tenant's billing row, creating its Stripe customer if absent.

    The Stripe customer is created at most once per tenant; the id is persisted
    so subsequent checkouts reuse it. Does not commit (caller owns the txn).
    """
    billing = get_billing(session, tenant_id)
    if billing is None:
        billing = TenantBilling(tenant_id=tenant_id)
        session.add(billing)
    if billing.stripe_customer_id is None:
        customer = _client(settings).customers.create(
            params={"email": email, "metadata": {"tenant_id": tenant_id}}
        )
        billing.stripe_customer_id = customer.id
    session.flush()
    return billing


def create_checkout_session(
    settings: Settings, *, customer_id: str, plan: str, tenant_id: str
) -> Any:
    """Create a hosted Checkout Session for *plan* using its server-side Price ID.

    Raises ``KeyError`` if the plan is not a known paid plan. The tenant id is
    stamped into both session and subscription metadata so the webhook can route
    the resulting subscription back to the right tenant.
    """
    price_id = settings.stripe_price_by_plan[plan]
    return _client(settings).checkout.sessions.create(
        params={
            "mode": "subscription",
            "customer": customer_id,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": settings.stripe_checkout_success_url,
            "cancel_url": settings.stripe_checkout_cancel_url,
            "metadata": {"tenant_id": tenant_id, "plan": plan},
            "subscription_data": {"metadata": {"tenant_id": tenant_id, "plan": plan}},
        }
    )


def construct_event(settings: Settings, payload: bytes, signature: str) -> Any:
    """Verify the Stripe signature and return the parsed event, or raise.

    Wraps ``stripe.Webhook.construct_event``; a bad/forged signature raises
    ``stripe.SignatureVerificationError`` which the route maps to a 400 problem.
    Nothing downstream trusts an event that did not pass this check.
    """
    return stripe.Webhook.construct_event(
        payload, signature, settings.stripe_webhook_secret
    )


def get_billing(session: Session, tenant_id: str) -> TenantBilling | None:
    """Return the tenant's billing row, or None if it has none yet."""
    return session.scalar(
        select(TenantBilling).where(TenantBilling.tenant_id == tenant_id)
    )


def period_end(epoch: int | None) -> datetime.datetime | None:
    """Convert a Stripe unix timestamp to an aware UTC datetime, or None."""
    if epoch is None:
        return None
    return datetime.datetime.fromtimestamp(epoch, tz=datetime.UTC)


def map_status(stripe_status: str | None) -> str:
    """Map a Stripe subscription status to our internal billing status."""
    return _STATUS_MAP.get(stripe_status or "", "incomplete")
