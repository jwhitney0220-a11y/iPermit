# 04 — Rules Engine

**Status:** Placeholder
**Owner ticket(s):** T03-01, T03-02, T03-03, T03-04, T03-05, T03-06 (all of EPIC-03)

---

## What This Section Will Cover

Engineer-facing documentation for the deterministic rules engine: how the parser consumes rule objects, how the evaluator walks the six-step evaluation order, how conflicts between overlapping jurisdictions are resolved, how the sequencer renders prerequisites into a workflow, how explainability is generated, and how known-unknowns are surfaced. It will be the primary reference for anyone modifying engine internals.

The section will be broken into sub-sections that mirror the EPIC-03 ticket structure:

### 4.1 Parser

What `rules/effective/*.yaml` files are loaded, how they are validated against the schema, how invalid rules are rejected, how the field registry is enforced.

**[Pending: filled when T03-01 ships. Owner: T03-01]**

### 4.2 Evaluator

The runtime walk through the six-step evaluation order from `AGENTS.md` *Rule Object Specification* (jurisdiction → temporal → project type → triggers → spatial → dependencies). How short-circuiting works. How `project.*`, `geometry.*`, and `derived.*` values are resolved.

**[Pending: filled when T03-02 ships. Owner: T03-02]**

### 4.3 Conflict Resolution

How two rules from different jurisdiction levels are reconciled when they produce conflicting outputs. How the *lower jurisdictions may add but not silently delete* rule from `AGENTS.md` *Rules Engine Architecture* is enforced. How `supersedes` and `superseded_by` are resolved.

**[Pending: filled when T03-03 ships. Owner: T03-03]**

### 4.4 Sequencer

How `sequencing.prerequisites` and `sequencing.parallel_with` are turned into a permit workflow. How cycles are detected and reported. How lead times are aggregated.

**[Pending: filled when T03-04 ships. Owner: T03-04]**

### 4.5 Explainability

How `explanations.trigger_explanation`, citations, confidence tier, and the short-circuit reason are assembled into the consultant-facing explanation. What the explainer output looks like.

**[Pending: filled when T03-05 ships. Owner: T03-05]**

### 4.6 Known-Unknowns

How `known_unknowns` are surfaced in the permit matrix and what triggers an "additional review recommended" flag on a permit row.

**[Pending: filled when T03-06 ships. Owner: T03-06]**

---

## What to Consult Instead

Until these sub-sections are authored, consult:

- [`AGENTS.md`](../../AGENTS.md) — *Rules Engine Architecture*, *Rule Object Specification*, *Temporal Versioning*, and *Permit Confidence Tiers*. These define what the engine MUST and MUST NOT do; the implementation must conform.
- [`docs/specs/rule-object.md`](../specs/rule-object.md) — the input contract. Anything the engine reads is defined here.
- [`docs/roadmap.md`](../roadmap.md) — EPIC-03 ticket descriptions for the intended scope of each engine component.
- [`docs/engineering-handbook/05-editing-rules-safely.md`](./05-editing-rules-safely.md) — explains how authors interact with the engine indirectly through rule files.

## Safe Today vs. Requires Design Work

Until any of EPIC-03 ships, you can:

- Author rule objects in `rules/draft/` and validate them against the schema.
- Discuss engine design in PR comments on EPIC-03 tickets.

You cannot:

- Run a permit evaluation. There is no engine yet.
- Test that a rule "fires correctly." The benchmark and regression framework (T04-02) depends on the engine existing.

When a sub-section above is authored, the author should remove the corresponding *Pending* line, update the parent *Status* if appropriate, and update the handbook [README](./README.md) table of contents.
