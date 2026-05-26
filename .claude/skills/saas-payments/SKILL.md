---
name: saas-payments
description: Use when integrating billing — Stripe or Lemon Squeezy plans, checkout, subscription webhooks, entitlement gating, or usage metering.
---

# saas-payments — billing & metering

**Reference:** open-saas `template/app/src/payment` (`paymentProcessor`, `plans`, `webhook`, `operations`) — the cleanest pattern for processor-agnostic billing.

## Conventions
- Put the processor behind an interface (Stripe first); keep plan definitions in one module.
- Checkout creates a session server-side; **never trust client-supplied price/plan** — resolve entitlements server-side.
- Webhooks: verify the signature, handle idempotently (dedupe by event id), and bind every event to a tenant before mutating subscription state.
- Entitlements gate features and quotas by plan; meter billable actions (evaluations, exports) per tenant.

## Guardrails
- **MANDATORY** security-review (webhook signature, replay/idempotency, tenant binding, no secret leakage).
- Use the **saas-multitenancy** skill for the tenant binding and the **saas-frontend** skill for the pricing page.
- Functions ≤ 60 lines; secrets via env (`*_SECRET_REF`), never committed.
