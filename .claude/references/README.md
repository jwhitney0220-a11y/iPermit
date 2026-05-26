# .claude/references/

Read-only third-party checkouts used as **reference patterns** for iPermit
development. They are git-ignored (not committed — they would bloat history and
mix foreign stacks into this Python repo) and re-cloned on demand.

| Reference | Clone command | Why |
|-----------|---------------|-----|
| `open-saas` | `git clone --depth 1 https://github.com/wasp-lang/open-saas .claude/references/open-saas` | Canonical open-source SaaS feature set (auth, payments, file upload, admin, analytics, email, deploy). Used to shape `docs/saas-roadmap.json`. NOTE: open-saas is a Wasp/Node/Prisma stack — it is a **pattern reference only**; iPermit's chosen stack is FastAPI + React + Postgres (ADR-0001). |

These are not dependencies and are never imported by iPermit code.
