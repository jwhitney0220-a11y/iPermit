# 08 — Debugging

**Status:** Placeholder
**Owner ticket(s):** T03-05 (explainability engine), and follow-on debugging-tooling tickets in later EPICs

---

## What This Section Will Cover

The day-to-day debugging playbook for engineers and analysts when a permit output looks wrong. Specifically:

- How to trace a single permit evaluation end-to-end: which rule fired, which step in the six-step evaluation order short-circuited the other candidates, which input value (`project.*`, `geometry.*`, `derived.*`) drove the trigger.
- How to read the explainability output (owned by T03-05) and map it back to a specific rule file and version.
- How to reproduce a consultant's exact evaluation locally using the audit log (T01-04) and the historical ruleset (`rules/archived/` + the temporal model from T00-03 / T02-04).
- How to distinguish among the three common failure modes: (a) engine bug, (b) rule authoring bug, (c) input data bug (wrong project type, misdetected jurisdiction, missing GIS overlay).
- Common pitfalls — e.g., a rule that "isn't firing" but is actually short-circuited by a jurisdiction mismatch upstream — and the diagnostic steps that surface them quickly.
- Tooling: the analyst QA dashboard (T04-05), the simulation engine (T04-01), and any CLI utilities the engineering team builds for one-off traces.

## [Pending: filled after T03-05 ships. Owner: T03-05 plus follow-on tooling]

This section cannot be authored until the explainability engine (T03-05) exists, because debugging in iPermit *is* reading the explainability output and following its citations back to the rule file. Without an explainer, there is no trace to read.

Once T03-05 ships, this section will likely also depend on:

- T04-01 (simulation) for "what would have fired if input X were different" debugging.
- T04-05 (analyst QA dashboard) for the UI-driven debugging path.
- T01-04 (audit logging) for reproducing historical evaluations.

## What to Consult Instead

Until this section is authored, debugging is necessarily ad hoc. Useful starting points:

- [`docs/specs/rule-object.md`](../specs/rule-object.md) §8 (Rule Evaluation Order) — when you suspect a rule is not firing, walk the six steps in order and identify the first one that fails. The same procedure will be automated by the explainer.
- [`AGENTS.md`](../../AGENTS.md) *Rules Engine Architecture* — the jurisdiction hierarchy and the "lower jurisdictions may add but not silently delete" constraint explain most cross-jurisdiction surprises.
- [`docs/engineering-handbook/01-engineering-standards.md`](./01-engineering-standards.md) §5 — the "explicit logic over hidden magic" rule means every engine decision should be traceable by reading the code with a breakpoint. If you cannot find where a decision is made, that itself is a bug.
- [`docs/engineering-handbook/05-editing-rules-safely.md`](./05-editing-rules-safely.md) §6 — common rule authoring mistakes. Many "engine bugs" turn out to be rule bugs.

## Safe Today vs. Requires Design Work

Today the only debugging surface is reading rule YAML, reading service code (as it gets written), and using a normal debugger or print statements. There is no purpose-built tracing yet.

When you find yourself wanting structured tracing — "show me every rule the engine considered for this project and why each one fired or didn't" — that is the explainer (T03-05). Wait for it; do not build a parallel tracing layer that the explainer will then duplicate.

When this section is authored, the author should remove the *Pending* line, update the *Status*, and refresh the handbook [README](./README.md) table of contents.
