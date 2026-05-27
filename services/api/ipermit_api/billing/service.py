"""Subscription state service (SAAS-03 / S03-01).

Applies a verified webhook event to the tenant's subscription, idempotently: the
provider event id is recorded so replays are no-ops (processors retry webhooks).
The DB write is the system path (no tenant GUC), which the subscription RLS
policy admits.
"""

from __future__ import annotations

import datetime
import uuid

from ipermit_tenancy import Subscription, WebhookEvent
from sqlalchemy import select
from sqlalchemy.orm import Session

from .provider import WebhookEventData


def apply_event(session: Session, event: WebhookEventData) -> Subscription | None:
    """Upsert the tenant's subscription from *event*; return None if a replay.

    Flushed, not committed — the caller owns the transaction and the audit record.
    """
    if session.get(WebhookEvent, event.event_id) is not None:
        return None
    session.add(WebhookEvent(event_id=event.event_id, event_type=event.event_type))
    sub = session.scalar(
        select(Subscription).where(Subscription.tenant_id == event.tenant_id)
    )
    if sub is None:
        sub = Subscription(subscription_id=uuid.uuid4().hex, tenant_id=event.tenant_id)
        session.add(sub)
    sub.plan = event.plan
    sub.status = event.status
    sub.external_customer_id = event.external_customer_id
    sub.external_subscription_id = event.external_subscription_id
    sub.updated_at = datetime.datetime.now(tz=datetime.UTC)
    session.flush()
    return sub
