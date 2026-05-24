# 05 — Editing Rules Safely

**Status:** Partial — authoring procedure authored; analyst review workflow pending T00-09
**Source guardrails:** [`AGENTS.md`](../../AGENTS.md) sections *Rules Engine Architecture*, *Temporal Versioning*, *Human Review Workflow*
**Related tickets:** T00-01 (rule object spec — shipped), T00-06 (benchmark suite), T00-09 (analyst SOP), T08-04 (publication workflow)

---

## 1. The Cardinal Rule

Engineering PRs do not edit `rules/published/` or `rules/effective/`. Ever. Those directories are owned by the publication workflow (T08-04) and reflect rules that are governing real consultant evaluations. An engineering PR that touches them is a bug, even if the change looks trivial.

If you find a typo or broken citation in a published rule, file an analyst ticket. Do not "fix" it in code.

## 2. Where Engineering Can Edit Rules

Today, the only place engineering may edit rule files directly is `rules/draft/`. Drafts are:

- Under active development by their authoring analyst.
- Not yet reviewed.
- Not loaded by the runtime engine (when the engine exists).
- Allowed to fail schema validation transiently, though they MUST pass before being promoted.

Even within `rules/draft/`, an engineer editing a rule should be paired with or have explicit consent from the authoring analyst. The analyst is responsible for regulatory accuracy (`AGENTS.md` *Regulatory Analyst SOP Requirements*); the engineer's role on a rule file is shape and schema.

## 3. Adding a New Draft Rule — Step by Step

This procedure assumes the rule object spec (T00-01) has shipped and the schema is at `docs/specs/schemas/rule-object.schema.json`.

1. **Branch from `main`.** Name the branch `rule/<jurisdiction>-<short-name>` (e.g. `rule/tx-county-floodplain`).
2. **Pick a `rule_id`.** Follow the convention in [`docs/specs/rule-object.md`](../specs/rule-object.md) §5.1: lowercase kebab-case, prefixed by jurisdiction. Confirm it is not already used by searching `rules/` recursively. IDs are never reused.
3. **Create `rules/draft/<rule_id>.yaml`.**
4. **Fill in the required fields** from the spec §6 (Required-Field Summary). Use the reference example at `docs/specs/examples/rule-object-example.yaml` as a starting point.
5. **Validate locally** against the JSON Schema:

   ```bash
   python3 -c "
   import json, yaml, jsonschema
   schema = json.load(open('docs/specs/schemas/rule-object.schema.json'))
   rule = yaml.safe_load(open('rules/draft/<rule_id>.yaml'))
   jsonschema.Draft202012Validator(schema).validate(rule)
   print('valid')
   "
   ```

   This same validation runs in CI under T01-07.

6. **Run the benchmark suite** (once T00-06 has shipped fixtures and T04-02 has shipped the runner). Until the runner ships, this step is "the suite is not yet executable; document any benchmark cases your rule should hit in the PR description so they can be wired in later."
7. **Open a PR** with the changes confined to `rules/draft/`. Tag the authoring analyst as the responsible reviewer.

## 4. Modifying an Existing Draft Rule

Same procedure as §3, except step 2 is skipped. Bump the `version` field per the spec §5.1 rules: MAJOR if trigger logic or outputs change materially, MINOR for non-breaking detail, PATCH for typos and citation refresh.

If your change to a draft rule turns it into a *replacement for* a previously published rule, that is a regulatory event, not an edit — it goes through the publication workflow (T08-04). Stop and consult the authoring analyst.

## 5. What "Safe" Means

A change to a rule file is *safe* when all of the following are true:

- The file is in `rules/draft/`.
- The new content validates against `docs/specs/schemas/rule-object.schema.json`.
- The `rule_id` was either already present (you are editing an existing draft) or is genuinely new (you are creating a draft).
- No field references a jurisdiction ID, project field path, or trigger operator that is not defined in its owning registry. (Jurisdiction IDs: T00-02 / T00-08. Project field paths: T02-02 + T06-02 + T05-04. Trigger operators: spec §7.)
- The PR description names the regulatory source(s) the change is based on and links the citation.
- The benchmark project(s) that should exercise this rule are named, even if the runner isn't yet executable.

A change is *unsafe* if it touches `published/` or `effective/`, if it silently broadens or narrows a trigger without bumping `version`, or if it changes citations without updating `provenance.last_verified`.

## 6. Common Mistakes

- **Reusing a `rule_id`.** Never. A regulation that changed is a new version of the same rule (bumped `version`); a regulation that replaced an older one is a new rule with a new ID and `supersedes` pointing at the old.
- **Editing `provenance.last_verified` without re-verifying.** The date means "an analyst confirmed every citation on this date." Bumping the date because the file changed is data fraud. Leave the date alone unless verification happened.
- **Encoding logic in advisory strings.** `advisories[]` is for mandatory display text. It is not for "if X then say Y" branching. If you find yourself wanting branching, you need additional rule objects or richer triggers.
- **Letting a draft schema-fail at PR time.** Drafts may transiently fail mid-edit, but the PR for merging MUST pass schema validation. If you cannot make it valid yet, keep working on your branch.

## 7. Analyst Review Workflow

**[Pending: filled when T00-09 ships. Owner: T00-09 (Regulatory Analyst SOP Manual)]**

The analyst-facing review procedure — source collection, normalization checks, peer review, publication approval, emergency updates — is owned by T00-09. Until T00-09 ships, the working assumption is:

- Engineering review confirms schema validity and code-side correctness.
- The authoring analyst's manager (or a second analyst) confirms regulatory accuracy.
- No rule moves out of `draft/` until both are satisfied and T08-04 publication tooling exists.

**Consult instead:**

- [`AGENTS.md`](../../AGENTS.md) *Human Review Workflow*, *Regulatory Analyst SOP Requirements*.
- [`docs/specs/rule-object.md`](../specs/rule-object.md) §9 (Lifecycle Transitions) and §12 (Change Control).

When T00-09 ships, this section will be replaced with the concrete SOP and the *Pending* line removed.
