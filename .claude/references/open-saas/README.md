# open-saas reference (pattern-only)

Source patterns copied from [wasp-lang/open-saas](https://github.com/wasp-lang/open-saas)
@ `b681f1b` (MIT, see `LICENSE`). **Reference only — do not run or import.**

open-saas is **Wasp / Node / Prisma**. iPermit's stack is **FastAPI + React/TS +
Postgres/PostGIS** (ADR-0001). These files are studied as feature *patterns* when
authoring the equivalent iPermit skills; nothing here is part of the build.

## What's cloned now (per `docs/roadmap/saas-v1-skills-needed.json` clone_now)

- `auth/` — login/signup/password-reset/email-verify flows, signup fields → pattern for the **saas-auth** skill (ADR-0002).
- `client/` — SPA shell, NavBar, routing, shadcn/ui components → pattern for the **saas-frontend** skill (ADR-0001). Static image assets stripped.

## Deferred clones (pull when the epic starts)

- `payment/` → SAAS-03 (saas-payments)
- `file-upload/` → SAAS-04 (saas-file-upload)
- `admin/`, `analytics/` → SAAS-05 (saas-admin-portal, saas-analytics)
- `user/`, `emailSender` → SAAS-04 / SAAS-07
