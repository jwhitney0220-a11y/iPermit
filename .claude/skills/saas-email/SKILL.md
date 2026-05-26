---
name: saas-email
description: Use when adding transactional email — account verification, password reset, or workflow notifications.
---

# saas-email — transactional email

**Reference:** open-saas emailSender configuration (provider-agnostic sender).

## Conventions
- Put the provider behind an interface (SMTP / SES / Resend); template the bodies.
- Sends are idempotent. Verification and password-reset tokens are single-use and expiring; bind them to the user and invalidate on use.
- Config/secrets via env (`AUTH_*` / email vars per `.env.example`); never commit credentials.

## Guardrails
- security-review for any token-bearing flow (reset/verify) — pairs with **saas-auth**.
- Rate-limit sends; never include secrets or full tokens in logs. Functions ≤ 60 lines.
