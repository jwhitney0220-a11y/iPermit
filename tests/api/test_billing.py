"""Billing tests (SAAS-03 / S03-01): checkout, subscription, signed webhooks.

The webhook path is the security-critical surface: signatures are HMAC-verified
and processing is idempotent. The stub provider signs payloads the same way, so
these exercise the real verification code without external calls.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from ipermit_api.billing.provider import StubPaymentProvider
from ipermit_api.settings import get_settings

_SECRET = get_settings().billing_webhook_secret


def _signed(body: dict) -> tuple[bytes, str]:
    payload = json.dumps(body).encode()
    return payload, StubPaymentProvider(_SECRET).sign(payload)


def _event(tenant_id: str, plan: str = "pro", event_id: str = "evt_1") -> dict:
    return {
        "event_id": event_id,
        "type": "subscription.updated",
        "tenant_id": tenant_id,
        "plan": plan,
        "status": "active",
        "external_customer_id": "cus_1",
        "external_subscription_id": "sub_1",
    }


def test_default_subscription_is_free(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    resp = client.get(
        "/api/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["plan"] == "free"


def test_checkout_returns_url(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    resp = client.post(
        "/api/v1/billing/checkout",
        json={"plan": "pro"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert seeded["tenant_a"] in resp.json()["checkout_url"]


def test_checkout_rejects_unknown_plan(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    resp = client.post(
        "/api/v1/billing/checkout",
        json={"plan": "platinum"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_webhook_rejects_bad_signature(client: TestClient, seeded: dict) -> None:
    payload, _ = _signed(_event(seeded["tenant_a"]))
    resp = client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Webhook-Signature": "deadbeef"},
    )
    assert resp.status_code == 400


def test_webhook_updates_subscription(client: TestClient, seeded: dict, login) -> None:
    payload, sig = _signed(_event(seeded["tenant_a"], plan="pro"))
    resp = client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Webhook-Signature": sig},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    token = login(seeded["email_a"])
    sub = client.get(
        "/api/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert sub["plan"] == "pro"
    assert sub["monthly_evaluations"] == 500


def test_webhook_is_idempotent(client: TestClient, seeded: dict) -> None:
    payload, sig = _signed(_event(seeded["tenant_a"], event_id="evt_dup"))
    headers = {"X-Webhook-Signature": sig}
    first = client.post("/api/v1/billing/webhook", content=payload, headers=headers)
    second = client.post("/api/v1/billing/webhook", content=payload, headers=headers)
    assert first.json()["status"] == "ok"
    assert second.json()["status"] == "duplicate"
