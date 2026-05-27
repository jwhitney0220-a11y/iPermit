---
name: saas-payments
description: >
  Build iPermit billing on Stripe — plans, checkout, subscription webhooks,
  entitlement gating, and per-tenant usage metering. Use for SAAS-03 tickets
  (S03-01..04). FastAPI + Postgres; open-saas src/payment is the feature pattern.
  Security-gated (webhooks + money).
---

# saas-payments — Stripe billing for iPermit

Provider: **Stripe** (chosen for SAAS-03). Stack: FastAPI + Postgres (ADR-0001),
tenant-scoped (saas-multitenancy), auth-gated (saas-auth). Pattern reference:
`.claude/references/open-saas/payment` (Wasp/Node — note the
`paymentProcessor` abstraction + `stripe/webhook.ts` signature handling; translate
intent to Python/`stripe` SDK).

## Non-negotiables (security-gated — run security-review on every payments ticket)

- **Verify webhook signatures.** The `/webhooks/stripe` endpoint MUST verify the
  `Stripe-Signature` header against the endpoint signing secret
  (`stripe.Webhook.construct_event`) before trusting any event. Reject unverified.
- **Webhooks are the source of truth for entitlement**, not the client. Never set
  a tenant's plan/entitlement from a browser request or checkout redirect — only
  from a verified webhook event (`checkout.session.completed`,
  `customer.subscription.updated/deleted`, `invoice.paid`, etc.).
- **Idempotency.** Persist processed Stripe `event.id`s; ignore duplicates
  (Stripe retries). Use Stripe idempotency keys on create calls.
- **Never trust client amounts/prices.** Prices/plans come from server-side Stripe
  Price IDs (config), never from the request body.
- **Secrets** (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`) from env (T01-08);
  never hardcoded/committed. Use test keys in dev/CI.
- **Tests use the Stripe SDK in mock/stub mode** — do NOT hit the live API in CI.
  Stub the client; construct webhook payloads with a test-signed secret to
  exercise `construct_event`.

## Model (S03-01)

- Tenant-owned billing rows: Stripe `customer_id`, `subscription_id`,
  `plan`, `status`, `current_period_end`. One per tenant.
- `ProcessedStripeEvent` (event_id PK) for idempotency.
- Entitlement = derived from subscription status + plan; a `require_entitlement`/
  capability check (composes with saas-auth RBAC) gates premium routes (S03-02).

## Build checklist

1. Explore the API auth/tenancy/db wiring (`services/api/ipermit_api`); Plan the
   billing module + routes.
2. Models + Alembic migration (tenant-scoped billing + processed-events).
3. Stripe client wrapper (key from settings); checkout-session create route
   (auth-gated, server-side Price IDs); customer-portal route.
4. `/webhooks/stripe`: verify signature → idempotency check → handle event →
   update tenant entitlement. Audit each billing event (saas-audit).
5. Entitlement gating dependency (S03-02); pricing page (saas-frontend).
6. Usage metering per tenant (S03-03): count metered actions (e.g. evaluations),
   report to Stripe usage records or bill from internal counters.
7. Tests (stubbed Stripe): signature-verify rejects forged webhook; valid event
   updates entitlement; duplicate event ignored; gating denies without plan.
8. **security-review (S03-04)** + code-review; `run`/`verify`; commit.

## Reference

open-saas `payment/` (provider abstraction, plans, webhook); Stripe Python SDK.
