# Contributing to iPermit

iPermit is a consultant-focused permitting intelligence platform for Texas
utility and transmission projects. Before contributing, read
[`AGENTS.md`](./AGENTS.md) — it holds the locked strategic decisions, confidence
tiers, liability/advisory rules, and engineering standards that govern all work.

This guide covers: how to propose a change, the engineering standards you must
meet, how to run validation locally, the PR flow, and the separate path for
regulatory rule changes.

Related: branching and release process is in
[`docs/operations/branching-and-release.md`](./docs/operations/branching-and-release.md)
(T01-06). The regulatory analyst SOP is
[`docs/specs/analyst-sop.md`](./docs/specs/analyst-sop.md) (T00-09).

---

## 1. Proposing a Change

Start with an issue, not a PR. Pick the right template
([`.github/ISSUE_TEMPLATE/`](./.github/ISSUE_TEMPLATE)):

- **Bug report** — a defect in code or behavior.
- **Feature request** — a new capability or enhancement. Note its roadmap ticket
  and confirm it is in MVP scope and not on the AGENTS.md deferred list.
- **Regulatory rule add/change** — a new or changed permit, threshold, form,
  citation, or jurisdiction. This routes to the analyst review queue and does
  **not** auto-publish (see §6).

For anything touching architecture or the locked decisions, raise it in the
relevant epic discussion before writing code.

## 2. Engineering Standards

These are enforced by review now and by linters/CI as they ship (T01-02, T01-07).

- **Functions stay under 60 lines.** This is a hard rule from AGENTS.md
  *Engineering Standards* (T01-02). Functions should do one clear task, use the
  simplest logic that works, and avoid unnecessary abstraction. Readability over
  cleverness; explicit logic over hidden magic.
- **No business logic in clients.** The deterministic rules engine is the source
  of truth. Frontends and exports are thin presentation layers (ADR-0001).
- **Shared types come from generated schema models**, not hand-written shapes
  (T01-11). The JSON Schemas in
  [`docs/specs/schemas/`](./docs/specs/schemas) are canonical.
- **No authoritative or guarantee-style language** in consultant-facing output.
  Never "guaranteed compliance," "complete certainty," "final determination,"
  "certified," or "legal compliance certification" (AGENTS.md *Liability
  Strategy*). Use advisory phrasing: "likely required," "commonly encountered,"
  "additional review recommended."
- **The stack** is Python 3.11+/FastAPI services and TypeScript/React apps on
  PostgreSQL + PostGIS (ADR-0001).

## 3. Running Validation Locally

Validation tooling is delivered by T01-02 (linters, function-length check) and
T01-12 (developer experience scripts), and wired into CI by T01-07. Until those
scripts land in [`scripts/`](./scripts), run the equivalent checks by hand and
have a reviewer confirm. When they exist, the expected checks before opening a PR
are:

- **Linters and formatters** for the language you touched (Python and/or
  TypeScript).
- **Function-length check** — fails any function over 60 lines (T01-02).
- **Schema validation** for any rule or schema change, against
  [`docs/specs/schemas/rule-object.schema.json`](./docs/specs/schemas/rule-object.schema.json)
  (T00-01 §10; analyst SOP §4.5).
- **Tests** — unit tests for code; benchmark regression for rule changes once
  T04-02 ships.

CI runs the same checks on every PR; do not rely on CI to catch what you can run
locally.

## 4. The PR Flow

1. Branch from `main` using the naming convention in
   [`docs/operations/branching-and-release.md`](./docs/operations/branching-and-release.md)
   §2 — e.g. `feature/<ticket>-<slug>`. One ticket per branch where practical.
2. Implement, meeting the standards in §2 and §3.
3. Fill out the PR template
   ([`.github/pull_request_template.md`](./.github/pull_request_template.md)).
   Reference the roadmap ticket.
4. CI runs lint, function-length, schema validation, and tests (T01-07).
5. **At least one code-owner review** approves before merge
   ([`.github/CODEOWNERS`](./.github/CODEOWNERS)). Rule changes additionally
   require a regulatory-analyst reviewer who is not the drafting analyst
   (see §6).
6. Merge, then delete the branch.

Keep PRs single-purpose. Do not mix engine code and rule changes on one PR — split
them and merge code first, then rules
([repository strategy §4](./docs/engineering-handbook/02-repository-strategy.md)).

## 5. What Reviewers Will Reject

- A function over 60 lines.
- Business logic added to a client layer.
- Authoritative/guarantee-style language in consultant-facing output.
- Any change to `rules/published/` or `rules/effective/` made by hand (outside the
  publication workflow, T08-04).
- A rule change without source citations, a confidence tier, or a valid
  `jurisdiction_id`.

## 6. Regulatory Rule Changes Follow a Different Path

Rule data under [`rules/`](./rules) is governed by the regulatory analyst SOP
([`docs/specs/analyst-sop.md`](./docs/specs/analyst-sop.md), T00-09), not the
ordinary engineering flow. The essentials:

- **Authoring** happens on `analyst/<rule-id>-<version>` branches and lands in
  `rules/draft/` only (SOP §4).
- Every rule needs a **source citation** from the authority hierarchy
  (statute > regulation > agency rulemaking > guidance > website > form), a
  **jurisdiction**, and a **confidence tier** (SOP §2). Consultant feedback is a
  lead for investigation, never an authoritative citation.
- **Publication** — moving a rule from `draft/` to `published/` to `effective/` —
  is owned by the publication workflow (T08-04) and gated by analyst sign-off
  (SOP §8). It is never a routine engineering merge. No rule reaches consultants
  without provenance, explainability, passing benchmarks, an assigned confidence
  tier, and reviewer approval (AGENTS.md *Human Review Workflow*).
- Rule-change requests filed via the issue tracker enter the **analyst review
  queue** (T08-06, SOP §13) and do not auto-publish.

## 7. Commit and Branch Conventions

- Lowercase, hyphen-separated branch names; lead with the ticket ID
  (`feature/t03-02-...`). Agent-authored `claude/<topic>` branches are also in use
  and reviewed like feature branches.
- Reference the roadmap ticket in the commit message and PR description so the
  change traces back to the roadmap.

When in doubt, prefer the more cautious, more explainable, more traceable option —
that is the project's stated priority order (AGENTS.md *Technical Philosophy*).
