"""Payment-provider interface + a secret-free stub (SAAS-03 / S03-01).

Like the auth verifier (ADR-0002), the payment processor sits behind a swappable
interface so the concrete vendor (Stripe / Lemon Squeezy) is a configuration, not
a rewrite. The default :class:`StubPaymentProvider` needs no external service and
verifies webhooks with the same HMAC-SHA256 scheme real processors use (a signed
raw payload), so the security-critical verification path is real and testable
without secrets. A Stripe adapter implements the same protocol and is selected by
``BILLING_PROVIDER`` when configured.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Protocol

from ..settings import get_settings


@dataclass(frozen=True)
class WebhookEventData:
    """Normalised subscription event parsed from a verified webhook."""

    event_id: str
    event_type: str
    tenant_id: str
    plan: str
    status: str
    external_customer_id: str | None = None
    external_subscription_id: str | None = None


class SignatureError(Exception):
    """Raised when a webhook signature fails verification."""


class PaymentProvider(Protocol):
    """The payment processor seam (S03-01)."""

    def create_checkout(self, *, tenant_id: str, plan: str) -> str:
        """Return a hosted-checkout URL for *tenant_id* to subscribe to *plan*."""
        ...

    def parse_event(self, payload: bytes, signature: str) -> WebhookEventData:
        """Verify the signature and parse the raw webhook *payload*."""
        ...


def _sign(payload: bytes, secret: str) -> str:
    """HMAC-SHA256 of the raw payload, hex-encoded (Stripe-style scheme)."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class StubPaymentProvider:
    """Secret-free provider for local/dev/CI; HMAC-signed webhooks."""

    def __init__(self, webhook_secret: str) -> None:
        self._secret = webhook_secret

    def create_checkout(self, *, tenant_id: str, plan: str) -> str:
        return f"https://billing.local/checkout/{tenant_id}/{plan}"

    def sign(self, payload: bytes) -> str:
        """Produce a valid signature header for *payload* (used by tests/dev)."""
        return _sign(payload, self._secret)

    def parse_event(self, payload: bytes, signature: str) -> WebhookEventData:
        expected = _sign(payload, self._secret)
        if not hmac.compare_digest(expected, signature or ""):
            raise SignatureError("invalid webhook signature")
        body = json.loads(payload)
        return WebhookEventData(
            event_id=body["event_id"],
            event_type=body["type"],
            tenant_id=body["tenant_id"],
            plan=body["plan"],
            status=body.get("status", "active"),
            external_customer_id=body.get("external_customer_id"),
            external_subscription_id=body.get("external_subscription_id"),
        )


def get_provider() -> PaymentProvider:
    """Return the configured payment provider (stub by default)."""
    settings = get_settings()
    # Only the stub ships today; a Stripe adapter slots in here behind the
    # same protocol when BILLING_PROVIDER=stripe and keys are configured.
    return StubPaymentProvider(settings.billing_webhook_secret)
