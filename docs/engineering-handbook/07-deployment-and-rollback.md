# 07 — Deployment and Rollback

**Status:** Placeholder
**Owner ticket(s):** T01-07 (CI pipelines), T08-04 (regulatory publication workflow)

---

## What This Section Will Cover

The end-to-end procedure for shipping changes to staging and production, plus the rollback procedure for both engineering changes and rule publications. Specifically:

- How an engineering PR becomes a deployment: branch protection, release tagging, environment promotion (dev → staging → production), and the health checks that gate each promotion.
- How a rule publication moves from `published/` to `effective/`: who approves, what tests must pass, how the cutover is logged, and how the previous version is preserved.
- Rollback for engineering: how to revert a deployment, when to fix-forward instead, how to use feature flags.
- Rollback for rule publications: how to demote an `effective/` rule back to a prior version, how grandfathered evaluations are preserved during the rollback, how the audit trail captures the rollback event.
- Versioning conventions for service releases and rule sets, and how they tie together so a given consultant evaluation is fully reproducible.

## [Pending: filled after EPIC-01 + EPIC-08 ship. Owner: T01-07 + T08-04]

This section cannot be authored yet because:

- The CI/CD pipelines (T01-07) define what "deployment" even means. Until they exist, there is no concrete procedure to document.
- The regulatory publication workflow (T08-04) defines the rule cutover and rollback procedure. It explicitly owns the moves between `rules/<status>/` directories.
- The audit logging infrastructure (T01-04) is the mechanism by which rollbacks are recorded; it must exist before "how to rollback" can be written.

Speculative procedures would be worse than no procedures. Anything written before T01-07 and T08-04 ship would have to be discarded and rewritten.

## What to Consult Instead

For deployment safety questions today:

- [`AGENTS.md`](../../AGENTS.md) *Temporal Versioning* — defines the rule lifecycle and the requirement that historical evaluations remain reproducible. This implicitly constrains how rollback must work.
- [`AGENTS.md`](../../AGENTS.md) *Human Review Workflow* — establishes that no rule may be published without provenance, explainability, benchmark tests passing, reviewer approval, and an assigned confidence tier. The deployment procedure must enforce this gate.
- [`AGENTS.md`](../../AGENTS.md) *Repository Strategy* — calls out branch protection and protection of published rules.
- [`docs/engineering-handbook/02-repository-strategy.md`](./02-repository-strategy.md) §5 — what branch protection is expected to enforce until codified.
- [`docs/specs/rule-object.md`](../specs/rule-object.md) §9 — the four-state lifecycle transitions are the substrate the publication workflow operates on.
- [`docs/roadmap.md`](../roadmap.md) — T01-07 and T08-04 ticket descriptions.

## Safe Today vs. Requires Design Work

Today there is no production environment, so there is nothing to deploy or rollback. The safe action set is:

- Local development only.
- PRs land on `main`; `main` is the working trunk, not a deployable branch.

Everything else — staging, production, rule cutovers, hotfixes, feature flags, rollback procedures — requires T01-07 and T08-04 to ship first. Do not improvise a deployment procedure ahead of those tickets; raise the question on the owning ticket instead.

When this section is authored, the author should remove the *Pending* line, update the *Status*, and refresh the handbook [README](./README.md) table of contents.
