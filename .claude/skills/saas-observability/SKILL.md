---
name: saas-observability
description: Use when adding structured logging, metrics, error tracking, or alerting to the iPermit services.
---

# saas-observability — logs, metrics & alerts

## Conventions
- Structured JSON logs with correlation ids: request id, `tenant_id`, and the API envelope's `evaluation_id` — so a permit result is traceable end-to-end (supports the reproducibility contract).
- Metrics: request latency, error rate, and per-tenant usage. Error tracking (Sentry-style) on unhandled exceptions.
- Alerts on SLO breaches and on audit-chain anomalies (a broken `hash`/`prev_hash` link is a security event).

## Guardrails
- **Never** log secrets, tokens, passwords, or raw PII. Redact at the logger boundary.
- Keep logging cheap and non-blocking on the request path. Functions ≤ 60 lines.
- Pairs with **saas-audit** (tamper-evidence) and **saas-deploy** (where collectors run).
