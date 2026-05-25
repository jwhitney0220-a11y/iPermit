<!--
iPermit pull request template (T01-13).
Fill out the sections that apply. Delete sections that genuinely do not.
Branching and review standards: docs/operations/branching-and-release.md (T01-06).
-->

## Summary

<!-- What does this PR do and why? Reference the roadmap ticket, e.g. "Closes T03-02." -->

## Type of change

- [ ] Engineering change (code under `apps/`, `services/`, `packages/`, `scripts/`, `infrastructure/`)
- [ ] Rule authoring (files under `rules/draft/` only — see analyst checklist below)
- [ ] Documentation only
- [ ] Other (describe):

## Engineering checklist

- [ ] Every function is under 60 lines (AGENTS.md *Engineering Standards*, T01-02).
- [ ] Logic is explicit and readable; no unnecessary abstraction.
- [ ] Tests added or updated, and they pass locally.
- [ ] Linters and the function-length check pass locally (T01-02 / T01-07).
- [ ] No business logic added to client/presentation layers (it belongs in the
      rules engine; ADR-0001).
- [ ] Shared types come from generated schema models, not hand-written shapes
      (T01-11).

## Rule-change checklist (complete only if this PR touches `rules/`)

- [ ] Change is confined to `rules/draft/` — this PR does **not** move files into
      `rules/published/` or `rules/effective/` (that is the publication workflow,
      T08-04, not a normal PR).
- [ ] Schema validation passes against `docs/specs/schemas/rule-object.schema.json`
      (T00-01 §10; SOP §4.5).
- [ ] Source citations included with full URLs, formal references, and Wayback
      snapshots (SOP §2.2, §4.4).
- [ ] Source excerpt(s) establishing the trigger pasted into this PR (SOP §2.3).
- [ ] `confidence_tier` assigned and justified (SOP §2.4).
- [ ] `jurisdiction_id` resolves to a registered jurisdiction record (T00-08).
- [ ] Fires-positive and fires-negative benchmarks exist and pass (SOP §6.2).
- [ ] Analyst peer review requested from a non-drafting analyst (SOP §7).

## Advisory-language compliance

- [ ] No consultant-visible text uses "guaranteed," "complete certainty," "final
      determination," "certified," or "legal compliance certification"
      (AGENTS.md *Liability Strategy*; SOP §5.1).
- [ ] Outputs use advisory phrasing ("likely required," "commonly encountered,"
      "additional review recommended") where they assert applicability.

## Reviewers

<!--
At least one code owner must approve (CODEOWNERS).
Rule changes additionally require a regulatory-analyst reviewer who is not the
drafting analyst (T00-09 §1, §7).
-->

## Notes / risks / rollback

<!-- Migration steps, follow-up tickets, or anything a reviewer should watch. -->
