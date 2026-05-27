"""Billing tests: checkout, signature-verified webhooks, entitlement (S03-01).

Stripe is fully STUBBED — no network. The webhook path exercises the REAL
``stripe.Webhook.construct_event`` by signing payloads with the test webhook
secret (the inert ``whsec_test_PLACEHOLDER`` default); the checkout path
monkeypatches the ``billing`` seam so the customer/session creates never call
the API. Asserts the security invariants: forged signature rejected with no
state change, entitlement written only from verified webhooks, idempotency on
the event id, and tenant isolation (a webhook for A never mutates B).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from ipermit_api import billing as billing_core
from ipermit_api.settings import get_settings
from ipermit_tenancy import AuditRecord, ProcessedStripeEvent, TenantBilling
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

# The webhook secret the test app verifies against (settings default). Tests sign
# with this so the real construct_event accepts the payload.
WEBHOOK_SECRET = get_settings().stripe_webhook_secret


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Build a valid Stripe-Signature header for *payload* (t=...,v1=...)."""
    ts = int(time.time())
    signed = f"{ts}.".encode() + payload
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _event(event_type: str, obj: dict, event_id: str | None = None) -> bytes:
    """Serialise a Stripe-shaped webhook event body."""
    body = {
        "id": event_id or f"evt_{uuid.uuid4().hex}",
        "object": "event",
        "type": event_type,
        "data": {"object": obj},
    }
    return json.dumps(body).encode()


def _post_webhook(client: TestClient, payload: bytes, signature: str):
    return client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"Stripe-Signature": signature, "Content-Type": "application/json"},
    )


def _billing(factory: sessionmaker[Session], tenant_id: str) -> TenantBilling | None:
    with factory() as s:
        return s.scalar(
            select(TenantBilling).where(TenantBilling.tenant_id == tenant_id)
        )


class _FakeCheckout:
    def __init__(self) -> None:
        self.id = "cs_test_123"
        self.url = "https://checkout.stripe.com/c/pay/cs_test_123"


@pytest.fixture
def stub_stripe(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stub the billing Stripe seam so checkout never touches the network."""
    captured: dict = {}

    def _ensure_customer(session, settings, *, tenant_id, email):
        billing = billing_core.get_billing(session, tenant_id)
        if billing is None:
            billing = TenantBilling(tenant_id=tenant_id)
            session.add(billing)
        billing.stripe_customer_id = billing.stripe_customer_id or "cus_test_1"
        session.flush()
        return billing

    def _create_checkout_session(settings, *, customer_id, plan, tenant_id):
        captured["price_id"] = settings.stripe_price_by_plan[plan]
        captured["plan"] = plan
        captured["customer_id"] = customer_id
        return _FakeCheckout()

    monkeypatch.setattr(billing_core, "ensure_customer", _ensure_customer)
    monkeypatch.setattr(
        billing_core, "create_checkout_session", _create_checkout_session
    )
    return captured


def test_checkout_requires_auth(client: TestClient) -> None:
    """The checkout route is auth-gated (401 without a bearer token)."""
    resp = client.post("/api/v1/billing/checkout", json={"plan": "pro"})
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_checkout_uses_server_side_price_id(
    client: TestClient, login, seeded: dict, stub_stripe: dict
) -> None:
    """Checkout resolves the plan to a server-side Price ID, returns a url."""
    token = login(seeded["email_a"])
    resp = client.post(
        "/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["checkout_url"].startswith("https://checkout.stripe.com/")
    # The price id came from settings, not the request body.
    assert stub_stripe["price_id"] == get_settings().stripe_price_pro
    assert stub_stripe["plan"] == "pro"


def test_checkout_rejects_unknown_plan(
    client: TestClient, login, seeded: dict, stub_stripe: dict
) -> None:
    """A plan outside the server-side map is a 422 (no free-form prices)."""
    token = login(seeded["email_a"])
    resp = client.post(
        "/api/v1/billing/checkout", json={"plan": "enterprise"}, headers=_auth(token)
    )
    assert resp.status_code == 422


def test_checkout_does_not_grant_entitlement(
    client: TestClient,
    login,
    seeded: dict,
    stub_stripe: dict,
    factory: sessionmaker[Session],
) -> None:
    """Entitlement is NOT set by checkout — only by the later webhook."""
    token = login(seeded["email_a"])
    client.post("/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token))
    billing = _billing(factory, seeded["tenant_a"])
    assert billing is not None
    assert billing.plan == "free"
    assert billing.status == "none"


def test_webhook_rejects_forged_signature(
    client: TestClient, seeded: dict, factory: sessionmaker[Session]
) -> None:
    """A bad signature is rejected (400 problem) and changes no state."""
    payload = _event(
        "checkout.session.completed",
        {"metadata": {"tenant_id": seeded["tenant_a"], "plan": "pro"}},
    )
    resp = _post_webhook(client, payload, "t=123,v1=deadbeef")
    assert resp.status_code == 400
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert _billing(factory, seeded["tenant_a"]) is None
    with factory() as s:
        assert s.scalar(select(ProcessedStripeEvent)) is None


def test_webhook_missing_signature_header(client: TestClient, seeded: dict) -> None:
    """No Stripe-Signature header is also a 400 (cannot verify)."""
    payload = _event("checkout.session.completed", {"metadata": {}})
    resp = client.post("/api/v1/billing/webhook", content=payload)
    assert resp.status_code == 400


def test_checkout_completed_activates_plan(
    client: TestClient, seeded: dict, factory: sessionmaker[Session]
) -> None:
    """A verified checkout.session.completed upserts an active plan + audit."""
    payload = _event(
        "checkout.session.completed",
        {
            "metadata": {"tenant_id": seeded["tenant_a"], "plan": "pro"},
            "customer": "cus_a",
            "subscription": "sub_a",
        },
    )
    resp = _post_webhook(client, payload, _sign(payload))
    assert resp.status_code == 200, resp.text
    billing = _billing(factory, seeded["tenant_a"])
    assert billing is not None
    assert billing.plan == "pro"
    assert billing.status == "active"
    assert billing.stripe_subscription_id == "sub_a"
    with factory() as s:
        actions = set(s.scalars(select(AuditRecord.action)).all())
    assert "billing.subscription_activated" in actions


def test_subscription_updated_sets_plan_and_status(
    client: TestClient, seeded: dict, factory: sessionmaker[Session]
) -> None:
    """customer.subscription.updated maps Stripe status -> active entitlement."""
    period_end = int(time.time()) + 86400
    payload = _event(
        "customer.subscription.updated",
        {
            "id": "sub_a",
            "status": "active",
            "current_period_end": period_end,
            "metadata": {"tenant_id": seeded["tenant_a"], "plan": "starter"},
        },
    )
    resp = _post_webhook(client, payload, _sign(payload))
    assert resp.status_code == 200, resp.text
    billing = _billing(factory, seeded["tenant_a"])
    assert billing is not None
    assert billing.plan == "starter"
    assert billing.status == "active"
    assert billing.current_period_end is not None


def test_subscription_deleted_cancels(
    client: TestClient, seeded: dict, factory: sessionmaker[Session]
) -> None:
    """customer.subscription.deleted sets status canceled."""
    payload = _event(
        "customer.subscription.deleted",
        {
            "id": "sub_a",
            "status": "canceled",
            "metadata": {"tenant_id": seeded["tenant_a"], "plan": "pro"},
        },
    )
    resp = _post_webhook(client, payload, _sign(payload))
    assert resp.status_code == 200, resp.text
    billing = _billing(factory, seeded["tenant_a"])
    assert billing is not None
    assert billing.status == "canceled"


def test_duplicate_event_is_idempotent(
    client: TestClient, seeded: dict, factory: sessionmaker[Session]
) -> None:
    """A redelivered event id is a no-op the second time."""
    event_id = "evt_dup_1"
    first = _event(
        "customer.subscription.updated",
        {
            "id": "sub_a",
            "status": "active",
            "metadata": {"tenant_id": seeded["tenant_a"], "plan": "pro"},
        },
        event_id=event_id,
    )
    assert _post_webhook(client, first, _sign(first)).status_code == 200
    # Redeliver the SAME event id but with a downgrade payload; must be ignored.
    second = _event(
        "customer.subscription.deleted",
        {
            "id": "sub_a",
            "status": "canceled",
            "metadata": {"tenant_id": seeded["tenant_a"], "plan": "pro"},
        },
        event_id=event_id,
    )
    resp = _post_webhook(client, second, _sign(second))
    assert resp.status_code == 200
    assert resp.json()["status"] == "duplicate"
    billing = _billing(factory, seeded["tenant_a"])
    assert billing is not None
    assert billing.status == "active"  # unchanged by the duplicate delivery
    with factory() as s:
        count = len(s.scalars(select(ProcessedStripeEvent)).all())
    assert count == 1


def test_webhook_tenant_isolation(
    client: TestClient, seeded: dict, factory: sessionmaker[Session]
) -> None:
    """A webhook for tenant A never mutates tenant B's entitlement."""
    payload = _event(
        "checkout.session.completed",
        {
            "metadata": {"tenant_id": seeded["tenant_a"], "plan": "pro"},
            "subscription": "sub_a",
        },
    )
    assert _post_webhook(client, payload, _sign(payload)).status_code == 200
    assert _billing(factory, seeded["tenant_a"]) is not None
    # Tenant B got no billing row at all.
    assert _billing(factory, seeded["tenant_b"]) is None


def test_get_billing_defaults_to_free(client: TestClient, login, seeded: dict) -> None:
    """GET /billing returns free/none before any subscription."""
    token = login(seeded["email_a"])
    resp = client.get("/api/v1/billing", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"] == "free"
    assert body["status"] == "none"


def test_get_billing_reflects_webhook(client: TestClient, login, seeded: dict) -> None:
    """GET /billing reflects entitlement written by a verified webhook."""
    payload = _event(
        "checkout.session.completed",
        {"metadata": {"tenant_id": seeded["tenant_a"], "plan": "pro"}},
    )
    assert _post_webhook(client, payload, _sign(payload)).status_code == 200
    token = login(seeded["email_a"])
    resp = client.get("/api/v1/billing", headers=_auth(token))
    assert resp.json()["plan"] == "pro"
    assert resp.json()["status"] == "active"


def test_get_billing_requires_auth(client: TestClient) -> None:
    """GET /billing is auth-gated."""
    assert client.get("/api/v1/billing").status_code == 401
