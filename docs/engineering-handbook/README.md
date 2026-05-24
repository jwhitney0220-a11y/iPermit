# iPermit Engineering Handbook

**Ticket:** T00-07
**Status:** Scaffold — sections 01, 02 fully authored; 05, 06 partially authored; 03, 04, 07, 08 are pending placeholders.
**Audience:** Engineers contributing to the iPermit platform.
**Related guardrails:** [`/AGENTS.md`](../../AGENTS.md), [`/docs/roadmap.md`](../roadmap.md), [`/docs/specs/`](../specs/)

---

## 1. Purpose

The Engineering Handbook is the practical, engineer-facing companion to `AGENTS.md`. Where `AGENTS.md` defines strategic guardrails ("rules MUST be declarative"), this handbook explains how to act on them ("here is what to do when a function approaches 60 lines; here is what to consult before editing a rule").

Per AGENTS.md *Engineering Handbook Requirement*, the handbook MUST eventually cover:

1. Overall system architecture
2. Rules engine behavior
3. Database structure
4. Jurisdiction hierarchy logic
5. Confidence scoring logic
6. GIS overlay workflows
7. AI workflow boundaries
8. How to safely edit any function
9. How to safely add or modify permit rules
10. How to test rule changes
11. How to prevent breaking core engine behavior
12. Required QA/QC steps before deployment
13. Rollback and versioning procedures

This document is the scaffold. Most subsystems do not yet exist, so most sections are placeholders that name the ticket that will populate them.

## 2. Scope

In scope:

- Engineering standards (function length, readability, naming).
- Repository layout and the four-stage rules directory model.
- Pointers to the canonical specs already on `main` (notably the Rule Object Specification, T00-01).
- A skeleton for every required topic, with explicit owners for the still-unauthored sections.

Out of scope:

- Product or strategic decisions — those live in `AGENTS.md`.
- Roadmap sequencing — that lives in `docs/roadmap.md` and `docs/roadmap.json`.
- Normative data formats — those live in `docs/specs/`.

If a section in this handbook conflicts with `AGENTS.md`, **`AGENTS.md` wins**. File a PR to fix the handbook.

## 3. How This Document Relates to AGENTS.md

| Source | Role |
|--------|------|
| `AGENTS.md` | Strategic guardrails. Tells you *what is and isn't allowed*. |
| Engineering Handbook (this doc) | Implementation guidance. Tells you *how to comply with the guardrails day-to-day*. |
| `docs/specs/*.md` | Normative formats and contracts. Tells you *the canonical shape of an artifact*. |
| `docs/roadmap.md` / `roadmap.json` | Sequencing. Tells you *what is being built when and by which ticket*. |

When in doubt:

- For policy questions ("can a rule auto-publish from feedback?") → `AGENTS.md`.
- For shape questions ("what fields does a rule object require?") → `docs/specs/`.
- For sequencing questions ("when is the rules engine due?") → `docs/roadmap.md`.
- For everyday engineering questions ("how do I split a 70-line function?") → this handbook.

## 4. Table of Contents

| # | Section | Status | Owner ticket(s) |
|---|---------|--------|-----------------|
| 01 | [Engineering Standards](./01-engineering-standards.md) | Authored | T00-07 |
| 02 | [Repository Strategy](./02-repository-strategy.md) | Authored | T00-07 |
| 03 | [System Architecture](./03-architecture.md) | Placeholder | T01-01, T03-02 |
| 04 | [Rules Engine](./04-rules-engine.md) | Placeholder | T03-01 through T03-06 |
| 05 | [Editing Rules Safely](./05-editing-rules-safely.md) | Partial | T00-07 (this doc) + T00-09 |
| 06 | [Testing and QA/QC](./06-testing-and-qaqc.md) | Partial | T00-07 + EPIC-04 |
| 07 | [Deployment and Rollback](./07-deployment-and-rollback.md) | Placeholder | T01-07, T08-04 |
| 08 | [Debugging](./08-debugging.md) | Placeholder | T03-05 and later |

## 5. What You Can Safely Do Today

Even with most subsystems unbuilt, the following are safe and encouraged:

- Read `AGENTS.md` end-to-end before contributing.
- Read [`docs/specs/rule-object.md`](../specs/rule-object.md) — the rule object shape is already canonical.
- Follow the engineering standards in [section 01](./01-engineering-standards.md): 60-line functions, explicit logic, simple names.
- Place new rules in `rules/draft/` (see [section 02](./02-repository-strategy.md)).
- Validate any draft rule against `schemas/rule-object.schema.json` (per spec §10).

## 6. What Requires More Design Work

Any of the following requires the owning ticket to ship first; the placeholder section names that ticket:

- Wiring a rule into the runtime evaluation engine (T03-02 is not built).
- Promoting a rule from `draft/` to `published/` (publication workflow lives in T08-04).
- Running a regression suite against benchmark projects (framework is T04-02; benchmark *definitions* are T00-06).
- Standing up the spatial DB (T05-01, gated by T01-16).
- Adding any AI assistance step to a workflow (constraints in `AGENTS.md` *AI Strategy*; implementation gated by EPIC-09).

If a placeholder section's owning ticket has not shipped, treat the topic as a design conversation, not a code change. Open a discussion ticket or comment on the owning ticket rather than improvising.

## 7. Maintenance

This handbook is updated by the engineer who closes the owning ticket for each section. When a placeholder ticket ships:

1. Replace the placeholder content with the authored content.
2. Update the status in the table of contents above.
3. Update any cross-references in other sections.
4. Note the change in the PR description so the team knows the handbook section has gone live.

For typo fixes and minor clarifications, a normal PR is sufficient. For structural changes (adding or removing a section), update this README's table of contents in the same PR.
