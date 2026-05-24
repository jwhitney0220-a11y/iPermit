# Regulatory Analyst Standard Operating Procedure

**Ticket:** T00-09
**Status:** Draft — initial issue
**Audience:** Regulatory analysts (drafting, reviewing, publishing), engineering leads who supervise the rules pipeline
**Source guardrails:** [`/AGENTS.md`](../../AGENTS.md) sections *Regulatory Analyst SOP Requirements*, *Human Review Workflow*, *Liability Strategy*, *User Feedback Queue*, *Initial Dataset Seeding*, *Data Governance*, *Temporal Versioning*
**Related tickets:** T00-01 (Rule Object), T00-03 (Temporal Selection), T00-06 (Benchmarks), T00-08 (Jurisdiction Records), T01-14 (RBAC), T02-07 (Freshness), T03-03 (Conflict Resolver), T08-04 (Publication Tooling), T08-06 (Feedback Queue)

---

## 0. How to Use This Manual

This is an operational manual for human regulatory analysts working on iPermit. It assumes you have read `AGENTS.md` and `docs/specs/rule-object.md` (T00-01). Where another ticket owns a concept (schemas, RBAC, engine algorithms, tooling), this manual defers to that ticket and tells you which one. Do not redefine cross-ticket contracts inside a rule object — raise a spec change instead.

Anything in this manual that conflicts with `AGENTS.md` loses; `AGENTS.md` is the supreme source. File a correction issue against this SOP if you find a conflict.

The manual is organized in the order an analyst hits each step on a normal day: roles, source collection, normalization, drafting, validation, benchmarks, peer review, publication, transitions, emergencies, conflicts, freshness, feedback, audit, and a closing list of prohibited actions.

---

## 1. Roles and Responsibilities

iPermit recognizes three analyst roles. A single human can hold more than one role, but the **drafting analyst and reviewing analyst on the same rule MUST be different people**. RBAC enforcement is owned by T01-14; this manual defines the operational expectations.

### 1.1 Drafting Analyst

- Performs source collection, normalization, and rule drafting.
- Owns the initial population of every required field in the rule object (T00-01 §6).
- Owns the first internal validation pass (schema, citations, advisory language).
- Opens the pull request on a feature branch.
- Cannot self-approve. Cannot self-publish.
- Responds to peer review feedback and re-runs benchmarks after every material change.

### 1.2 Reviewing Analyst (Peer)

- Conducts the peer review described in §7.
- Must not be the drafting analyst on the same rule.
- Confirms citations, sanity-checks trigger logic, verifies the confidence tier, checks `known_unknowns`, and confirms advisory language complies with the AGENTS.md liability strategy.
- Signs off in the PR with a documented review comment (see §7.5) before the rule may proceed to publication.

### 1.3 Publishing Analyst

- Holds publication authority (RBAC role granted under T01-14).
- Verifies the full publication checklist (§8.2) is satisfied before moving a file from `rules/draft/` to `rules/published/` or `rules/effective/`.
- Records reviewer attribution in `provenance.reviewer` if not already populated.
- May be the same person as the reviewing analyst on a given rule, but may NOT be the drafting analyst.
- Owns the emergency publication path (§10) and is the only role permitted to apply the emergency tag.

### 1.4 Role Summary Matrix

| Action | Drafting | Reviewing | Publishing |
|--------|----------|-----------|------------|
| Create draft file under `rules/draft/` | yes | no | no |
| Schema validation locally | yes | yes | yes |
| Open PR | yes | no | no |
| Sign off on peer review | no | yes | no |
| Move file to `rules/published/` or `rules/effective/` | no | no | yes |
| Apply emergency tag | no | no | yes |

---

## 2. Source Collection

### 2.1 Source Authority Hierarchy

When multiple sources discuss the same requirement, prefer the higher tier. The lower a source sits in this hierarchy, the more it warrants corroboration from a higher source.

1. **Statute** — enacted law (e.g. Texas Water Code, U.S.C.). Highest authority.
2. **Regulation** — codified administrative rule (e.g. 30 TAC, 40 CFR).
3. **Agency rulemaking** — formal adopted rule packages, final orders, Federal Register notices.
4. **Agency guidance** — guidance documents, technical memos, official FAQs.
5. **Agency website** — non-rule content on an agency-controlled domain.
6. **Form** — the form itself (including its instructions sheet).

A Tier 1 rule (§2.4) MUST cite at least one source from levels 1–3. A Tier 2 rule SHOULD include a level 1–3 source where possible and MUST include at least one source from levels 1–4. A Tier 3 rule may cite any level but MUST include explicit `known_unknowns` describing what is not yet verified.

Consultant feedback, blog posts, conference materials, third-party summaries, AI-generated text, and crowdsourced wikis are **never** authoritative. They may inform investigation; they may not be the sole citation for a rule.

### 2.2 What to Capture Per Source

For every source you cite, record:

- **Full URL** — the exact URL you opened. Do not shorten or rewrite.
- **Retrieval date** — populate `provenance.source_citations[].retrieved_at` (YYYY-MM-DD).
- **Archived snapshot** — submit the URL to the Wayback Machine (`https://web.archive.org/save/<url>`) and keep the resulting snapshot URL in `reviewer_notes` or in a comment alongside the citation. Agency content is reorganized and silently edited; the snapshot is your evidence of what you read.
- **Citation in formal legal style** — populate `provenance.source_citations[].reference` using the conventional form for the source type:
  - Statute: `Tex. Water Code § 26.121`, `33 U.S.C. § 1344(a)`
  - Regulation: `30 TAC § 305.541`, `40 CFR § 122.26(b)(14)`
  - Ordinance: `Travis County Code § 82.301`
  - Agency guidance: `USACE Fort Worth District Regulatory Guidance Letter 23-01 (2023)`
  - Form: `TCEQ Form 20022, NOI for Construction Stormwater (rev. 2024-08)`
  - Website: `TPWD Wildlife Habitat Assessment Program — landing page` plus URL

### 2.3 Capturing the Underlying Text

For any statute, regulation, or ordinance section you cite, paste the *relevant excerpt* into the PR description (or an attached `evidence/` note linked from the PR). The reviewing analyst should not have to re-fetch the source to verify the trigger logic. Quote the exact sentence(s) that establish the trigger threshold or the permit requirement.

### 2.4 Confidence Tier Guidelines

Tiers come from `AGENTS.md` *Permit Confidence Tiers*. Use these decision rules when assigning a tier on a new rule:

- **Tier 1** — statutory or regulatory in nature, uniformly applied across the jurisdiction, threshold is unambiguous, agency interpretation is stable for at least 24 months. Example: USACE Section 404 nationwide permit thresholds.
- **Tier 2** — supported by a statute, regulation, or ordinance, but local implementation varies (county-by-county thresholds, ordinance interpreted differently by city staff, posted threshold differs from internal practice). Example: county floodplain development permits where each county's enforcement varies.
- **Tier 3** — informational only. The analyst has identified that a permit *may* apply, but cannot yet confirm threshold, agency interpretation, or whether it is routinely required. Tier 3 rules MUST carry `known_unknowns` and MUST carry an advisory that consultant confirmation is required.

If you are uncertain between two tiers, pick the lower (more cautious) tier and document the uncertainty in `reviewer_notes`.

---

## 3. Normalization

### 3.1 One Rule = One Permit

The fundamental normalization principle: a single rule object describes a single permit at one point in its versioning history. If a regulation establishes two distinct permits (e.g. a general permit and an individual permit) they are **two rules**, even when they share a citation.

### 3.2 When to Split a Regulation Into Multiple Rules

Split when:

- The regulation establishes multiple permit names or permit codes.
- The regulation establishes a tiered structure where different project sizes hit different permits (split per permit, not per threshold).
- The regulation crosses jurisdiction levels (a state rule with county-level delegations becomes one state rule plus county-specific rules where delegation alters the requirement).
- The trigger logic for two permits in the same regulation is sufficiently different that combining them would obscure the trigger explanation.

### 3.3 When to Consolidate

Consolidate when:

- Multiple sub-sections of an ordinance establish a single permit with multiple trigger conditions. Use composition (`all` / `any` / `not`) in `triggers` rather than separate rules.
- A regulation cross-references implementation details that do not change which permit applies (e.g. supplementary procedural requirements). Capture the cross-references in `provenance.source_citations[]` and surface practical effects through `advisories` or `known_unknowns`.

### 3.4 `rule_id` Naming Conventions

`rule_id` is permanent and never reused. Follow the schema regex `^[a-z][a-z0-9]*(-[a-z0-9]+)+$`. The recommended pattern is `<jurisdiction-token>-<subject>-<permit-shortname>`.

- Jurisdiction token: `us` for federal, `tx` for Texas, `tx-<county>` for a county, `tx-<municipality>` for a municipality, `tx-<district>` for a district. Use the canonical jurisdiction name from T00-08, lowercased and hyphen-joined; never abbreviate beyond the jurisdiction record's canonical short form.
- Subject token: short topical token (`floodplain`, `stormwater`, `row`, `air`, `species`).
- Permit shortname: the conventional consultant shorthand (`section-404`, `tpdes-msgp`, `dev-permit`).

Examples:

- `us-water-section-404-individual`
- `us-water-section-404-nationwide-12`
- `tx-stormwater-tpdes-msgp`
- `tx-travis-floodplain-development-permit`
- `tx-austin-row-excavation-permit`

If a jurisdiction renames or merges (T00-08 owns this), the `rule_id` does NOT change. The jurisdiction record carries the alias history; the rule remains stable.

### 3.5 Versioning Within a `rule_id`

Use semver as defined in T00-01 §5.1:

- **MAJOR** — trigger logic or output materially changes; a consultant evaluating a project might receive a different answer.
- **MINOR** — non-breaking additions (e.g. adding `known_unknowns`, expanding `advisories`, adding a new form link).
- **PATCH** — typos, citation refreshes, `last_verified` updates, URL substitutions.

A MAJOR bump creates a new rule object with a new file; the prior version transitions to `archived` with `superseded_by` set. Never mutate an effective rule in place to capture a MAJOR change (§14, §15).

---

## 4. Rule Drafting Workflow

Follow this sequence end-to-end for any new rule. Each numbered step is mandatory.

### 4.1 Create the Draft File

1. Branch off `main`: `git checkout -b analyst/<rule-id>-<version>` (e.g. `analyst/tx-travis-floodplain-development-permit-1.0.0`).
2. Create the file under `rules/draft/<rule-id>.yaml`. Prefer YAML on disk per T00-01 §5; the schema is the same.
3. Place exactly one rule per file.

### 4.2 Populate Every Required Field

Walk T00-01 §6 (the required-field summary) top to bottom. Populate:

- Identity (`rule_id`, `version`, `title`, `permit_name`).
- Classification (`jurisdiction_level`, `jurisdiction_id`, `source_agency`, `applicable_project_types`).
- `confidence_tier` per §2.4.
- `provenance.source_citations[]` (min 1; multiple for Tier 2/3 per §4.4) and `provenance.last_verified` (today, YYYY-MM-DD).
- `status: draft`.
- `triggers` (single condition or composition; keep depth ≤ 3 per T00-01 §5.5).
- `outputs.permits[]` (min 1, each with `name` and `agency`).
- `explanations.trigger_explanation` per §4.3.

Optional fields (`forms`, `submission`, `agencies`, `sequencing`, `known_unknowns`, `advisories`, `tags`, `notes`) — fill what is true and verifiable. Leave blank rather than guessing.

### 4.3 Write the `trigger_explanation`

The `trigger_explanation` is the consultant-facing sentence telling a non-engineer why this permit applies. Rules:

- ≤ 280 characters (schema-enforced).
- Plain English. No internal jargon. No field path references (`project.acreage` is for the engine, not the consultant).
- States the operative threshold or condition: *"This permit is likely required because the project crosses one or more streams and exceeds 1 acre of disturbance."*
- Uses advisory phrasing per §5.6 (`likely required`, `commonly encountered`, `additional review recommended`). Never `guaranteed`, `complete certainty`, `final determination`, or `legal compliance`.

A reviewing analyst should be able to read the `trigger_explanation` alone and decide whether the rule's logic is correctly captured.

### 4.4 Cite Sources

- Tier 1: at least one citation, and it MUST be a statute, regulation, or ordinance (citation_type one of `statute`, `regulation`, `ordinance`).
- Tier 2: at least two citations, at least one from levels 1–4 of §2.1.
- Tier 3: at least one citation, plus explicit `known_unknowns` describing what is not yet verified.

Every citation gets a `reference` string, a `url` if one exists, and a `retrieved_at` date. Archive snapshots go into `reviewer_notes` or the PR description per §2.2.

### 4.5 Run Schema Validation

From the repository root, validate against the canonical schema (T00-01 §10):

```bash
python3 -c "
import json, sys, yaml, jsonschema
schema = json.load(open('docs/specs/schemas/rule-object.schema.json'))
rule = yaml.safe_load(open('rules/draft/<rule-id>.yaml'))
jsonschema.Draft202012Validator(schema).validate(rule)
print('valid')
"
```

A non-zero exit means the rule is not draftable. Fix the violation; do not commit until validation passes.

### 4.6 Run Local Benchmark Regression

Benchmark project format is owned by T00-06. Two checks are required before opening the PR:

1. **Rule-fires check.** Identify at least one benchmark project where this rule should fire. Run the benchmark suite locally per T00-06's instructions and confirm the rule appears in that benchmark's outputs.
2. **Non-regression check.** Run the full benchmark suite and confirm no previously passing benchmark now fails because of your rule. If a benchmark output legitimately changed (e.g. you are correcting a missed permit), capture the diff in the PR description and flag it for peer review attention.

Attach raw benchmark output (or a link to it) to the PR per §6.

### 4.7 Commit and Open the PR

1. Stage only the rule file and any new benchmark fixtures you authored: `git add rules/draft/<rule-id>.yaml`.
2. Commit message format: `<rule-id> v<version>: <one-line summary>`.
3. Push the branch and open a PR targeting `main`.
4. PR description MUST include: source excerpts (§2.3), the archive snapshot URLs, the benchmark output, the rationale for the confidence tier, and any deviations from this SOP.
5. Request a peer review from a non-self analyst (§7). Tag the publishing analyst for awareness but do not request publication yet.

---

## 5. Internal Validation Checklist

Run this checklist yourself before requesting peer review. The reviewing analyst will repeat it.

- [ ] Schema validation passes (§4.5).
- [ ] Every citation `url` opens in a browser and returns the cited content. Dead links MUST be replaced before review.
- [ ] Every citation has a Wayback Machine snapshot recorded.
- [ ] `trigger_explanation` is plain language, ≤ 280 chars, and accurately mirrors the trigger logic.
- [ ] `confidence_tier` is justified per §2.4 and consistent with the citations provided.
- [ ] `jurisdiction_id` resolves to a known record in the jurisdiction registry (T00-08). If the jurisdiction does not yet exist there, open a T00-08 record first; do not invent IDs.
- [ ] `applicable_project_types[]` uses tokens from the registry owned by T02-02. If a new token is required, raise a T02-02 change first.
- [ ] Advisory language complies with AGENTS.md liability strategy. Specifically: no `guaranteed`, `complete`, `final`, `certified`, `compliance certification`. Use `likely required`, `commonly encountered`, `additional review recommended`.
- [ ] `provenance.last_verified` is today's date.
- [ ] If `status` is `effective` or `archived`, `effective_from` is populated (schema-enforced, but verify the date is correct).
- [ ] Trigger composition depth ≤ 3 levels. If you need more, refactor.

### 5.1 Liability Language Quick Reference

| Use | Do NOT use |
|-----|------------|
| likely required | guaranteed |
| commonly encountered | always required |
| recommended workflow sequencing | the correct workflow |
| additional review recommended | no further action needed |
| advisory | legal advice |
| consultant confirmation suggested | confirmed by the platform |

When in doubt, soften the language and add to `known_unknowns`.

---

## 6. Benchmark Testing

Benchmark format and tooling are owned by T00-06. This section covers the analyst's responsibilities; it does not redefine the benchmark schema.

### 6.1 Why Benchmarks Matter

Benchmarks are the contract between rule authors and the engine. They prove a rule fires when it should, does not fire when it should not, and continues to produce the expected output across rule changes. Benchmarks are immutable historical records (AGENTS.md *Benchmark Project Library*); you may add new benchmarks but you may not modify old ones.

### 6.2 Required Benchmarks for a New Rule

For every new rule, the drafting analyst must ensure:

- At least one **fires-positive** benchmark exists where this rule's `triggers` evaluate true and the rule is among the expected outputs.
- At least one **fires-negative** benchmark exists where the rule's `triggers` evaluate false (e.g. a project just under the threshold) and the rule is NOT in the expected outputs.

If such benchmarks do not exist, add them under T00-06's benchmark directory and include them in the PR.

### 6.3 Regression Process

1. Capture the pre-change benchmark suite output on the branch base.
2. Make the rule change.
3. Re-run the suite.
4. Diff the outputs. Any unintentional diff is a regression and blocks the PR.
5. Attach the diff to the PR description with explanatory commentary on any intentional changes.

### 6.4 Benchmark Failures During Peer Review

If a benchmark fails during review:

- The drafting analyst fixes the rule, re-runs benchmarks, and pushes a new commit.
- The reviewing analyst re-runs the peer review checklist (§7.4) on the new commit. Prior approvals on superseded commits do NOT carry forward to the new commit.

---

## 7. Peer Review

Peer review is the gate between drafting and publication. It is mandatory. No rule may move to `published/` or `effective/` without a documented peer sign-off.

### 7.1 Reviewer Eligibility

The reviewing analyst:

- MUST hold the regulatory analyst RBAC role (T01-14).
- MUST NOT be the drafting analyst on this rule.
- SHOULD have domain familiarity with the regulatory area being reviewed (water, air, species, ROW, etc.). If no domain-aligned reviewer is available, document the gap in `reviewer_notes` and surface it to the publishing analyst.

### 7.2 What the Reviewer Verifies

The reviewer independently confirms:

1. **Citations** — every cited URL opens and shows the cited content. The reference text matches the formal legal style for the source type (§2.2). Snapshots exist.
2. **Trigger logic** — read the `trigger_explanation`, then read the `triggers` block, and confirm they agree. Mentally walk a simple project through the conditions.
3. **Confidence tier** — the tier matches the §2.4 decision rules given the citations provided.
4. **`known_unknowns`** — are reasonable and complete. The reviewer adds any uncertainty the drafter missed.
5. **Advisory language** — `trigger_explanation` and every entry in `advisories` use compliant phrasing (§5.1).
6. **Field paths** — every `project.*`, `geometry.*`, or `derived.*` reference exists in the field registry. Unrecognized paths block review.
7. **Benchmarks** — fires-positive and fires-negative benchmarks exist and pass.

### 7.3 What the Reviewer MUST NOT Do

- The reviewer MUST NOT rewrite the rule themselves. Leave PR comments and let the drafter respond.
- The reviewer MUST NOT approve without re-running the local validation (§4.5) on the latest commit.
- The reviewer MUST NOT approve a rule whose `confidence_tier` is unjustified, even if the rest of the rule is well-drafted. The right action is to request a tier change.

### 7.4 Resolving Disagreement

If drafter and reviewer disagree on tier, trigger interpretation, or advisory wording:

1. Capture both positions in the PR.
2. Escalate to a third analyst (any non-conflicted analyst) for a tie-break opinion.
3. If still unresolved, escalate to the publishing analyst, whose decision is final on language and confidence tier and whose decision is documented in `reviewer_notes`.

Never merge a contested rule. Resolve first.

### 7.5 Sign-Off Form

The reviewing analyst leaves a top-level PR comment in this exact form (this is the artifact T08-04 publication tooling will look for):

```
Peer review for <rule-id> v<version>:
- Citations verified: yes
- Trigger logic correct: yes
- Confidence tier justified: yes
- Known unknowns reasonable: yes
- Advisory language compliant: yes
- Benchmarks pass: yes
- Reviewer: <initials or analyst id>
- Date: YYYY-MM-DD
```

Any `no` blocks publication.

---

## 8. Publication Approval

### 8.1 Who Publishes

Only the publishing analyst, per §1.3, may execute publication. RBAC enforcement is owned by T01-14; tooling for the file move is owned by T08-04. This SOP covers the procedural responsibilities.

### 8.2 Publication Checklist

The publishing analyst confirms, in order:

- [ ] (a) All required fields populated per T00-01 §6.
- [ ] (b) Schema validation passes against `docs/specs/schemas/rule-object.schema.json`.
- [ ] (c) Peer review sign-off comment (§7.5) exists and is from a non-drafter.
- [ ] (d) Full benchmark suite passes on the latest commit.
- [ ] (e) Provenance is complete: `source_citations[]` populated, `last_verified` set, and `provenance.reviewer` populated with the reviewing analyst's identifier (the publisher populates this if the reviewer did not).
- [ ] (f) Confidence tier assigned and consistent with §2.4.
- [ ] (g) Liability language compliant (§5.1) across `trigger_explanation`, `advisories`, and any free-text fields.

If any item fails, the publisher returns the PR to the drafter with the failing item identified. The publisher does NOT fix the rule themselves.

### 8.3 The Publication Move

When the checklist passes:

1. Update `status` from `draft` to `published` (or directly to `effective` per §8.4).
2. Move the file from `rules/draft/<rule-id>.yaml` to the matching directory.
3. Use the publication tooling (T08-04) for the move. Manual moves are permitted only when tooling is unavailable, and require a follow-up commit explaining the bypass.
4. Commit the move as a separate commit on the same PR (or a follow-up PR per T08-04's workflow) with message `publish: <rule-id> v<version>`.
5. Merge.

### 8.4 Direct Publication to `effective/`

If `effective_from` is today or earlier and the rule has no future-dated activation, the publishing analyst may set `status: effective` and place the file directly under `rules/effective/`. Otherwise, the rule lives under `rules/published/` and transitions to `effective` per §9.

### 8.5 Documenting Deviations

Any deviation from the checklist (e.g. publication with a Tier 2 rule whose third corroborating source could not be located) MUST be documented in `reviewer_notes` and in the PR description. Deviations are visible during audit (§14). Routine deviations require an SOP amendment, not a one-off workaround.

---

## 9. Effective Transitions

T00-03 owns the engine-side temporal selection algorithm. This section covers the analyst's responsibilities at the rule-data level.

### 9.1 Setting `effective_from`

- Set `effective_from` to the date the regulation legally takes effect. For a regulation adopted today with no future effective date, that is today.
- For agency-adopted rules with a published effective date in the future, use that future date and leave `status: published`.
- Never set `effective_from` to a date earlier than the regulation's true effective date. Historical replay (T00-03) depends on this.

### 9.2 The Transition

When a rule's `effective_from` date arrives:

1. The publishing analyst (or scheduled tooling under T08-04) updates `status` from `published` to `effective`.
2. The file moves from `rules/published/` to `rules/effective/`.
3. The prior effective version (if any) for the same `rule_id` transitions to `archived`:
   - `status: archived`.
   - `effective_to` set to the day before the new version's `effective_from`.
   - `superseded_by` set to `<rule-id>@<new-version>`.
   - The new version's `supersedes` array includes `<rule-id>@<old-version>`.
   - File moves to `rules/archived/`.

### 9.3 Analyst Verification After Transition

Within one business day of a transition:

- Verify the new file lives under `rules/effective/` and the prior version (if any) lives under `rules/archived/`.
- Run the benchmark suite to confirm temporal replay still produces historical outputs (T00-03 is responsible for the algorithm; you are responsible for catching regressions).
- Update `last_verified` on the newly effective rule to the transition date.

### 9.4 What You MUST NOT Do During Transition

- Do not edit the archived version's content. Archive is immutable (§14).
- Do not delete the archived file. Archive retention is required for replay.
- Do not skip the supersedes/superseded_by linkage. Without it, the engine cannot reconstruct history.

---

## 10. Emergency Updates

Emergencies are real but rare: an ordinance is amended overnight, an agency contact phone changes, a form URL goes 404, a court strikes down a regulation. The fast path exists; it does NOT bypass peer review.

### 10.1 What Qualifies as an Emergency

- A regulation has been amended or repealed and the existing rule now produces wrong outputs.
- An agency contact, submission URL, or form URL has changed and the existing rule sends consultants to a dead endpoint.
- A court order has stayed or vacated a regulation.
- A formal agency announcement reverses prior guidance.

Routine clarifications, minor typos, or anticipated future changes do NOT qualify. Use the standard workflow.

### 10.2 Fast-Path Workflow

1. **Hot-patch versioning.** Bump the rule version per §3.5. URL or contact changes are typically PATCH. Substantive trigger or output changes are MAJOR; archive the prior version per §9.2.
2. **Branch and draft.** Same as §4, but tag the PR title with `[EMERGENCY]` and identify the trigger event in the PR description (e.g. agency notice date, court order docket).
3. **Expedited peer review.** Still mandatory. Same checklist as §7, but reviewers prioritize the PR and target same-day turnaround. Disagreements still escalate per §7.4.
4. **Publication with emergency tag.** The publishing analyst publishes per §8 and adds an entry to `advisories[]`: *"Emergency update issued YYYY-MM-DD due to <trigger event>. Confirm current agency posture before submission."*
5. **Tag retention.** Add the tag `emergency-update` to `tags[]` for later auditing.

### 10.3 What Stays the Same in an Emergency

- Schema validation is still required.
- Peer review is still required.
- Benchmarks are still required to pass (add new benchmarks if the emergency exposes a gap).
- Liability language is still required to be compliant.
- Provenance is still required.

The fast path compresses turnaround; it does not remove gates.

### 10.4 Post-Emergency Backfill

Within five business days after an emergency publication:

- Confirm Wayback snapshots for all newly cited sources (§2.2).
- Add any benchmark fixtures that should have caught the gap.
- Open a retrospective issue noting what surveillance (T02-07 freshness, T08-06 feedback) missed the change.

---

## 11. Conflict Resolution

The engine resolves conflicts at evaluation time (T03-03). The analyst's job is to make sure conflicts are real, documented, and visible — not to encode resolution logic inside a rule.

### 11.1 What a Conflict Looks Like

Two rules in different jurisdictions produce different outputs for the same project context. Examples:

- A state rule says the threshold is 1 acre; a county rule says 0.5 acre.
- A federal nationwide permit appears to authorize an activity that a local ordinance separately requires a permit for.
- Two cities' ETJ rules both apply to the same project segment and disagree on submission method.

Per AGENTS.md *Rules Engine Architecture*, lower jurisdictions may add requirements but MUST NOT silently delete parent requirements. A genuinely conflicting *deletion* must be re-expressed as an additive or escalating rule.

### 11.2 Analyst Workflow on Suspected Conflict

1. **Confirm the conflict is real.** Re-read both source documents. Many apparent conflicts dissolve when you re-read closely (different scope, different definitions, different effective dates).
2. **Document the conflict.** In each affected rule, add an entry to `known_unknowns` describing the overlap and the other rule's `rule_id`. Optionally add a `tags` entry such as `overlap:<other-rule-id>`.
3. **Flag for engine-side handling.** Do NOT encode an `if-this-other-rule-fires-then-skip-me` style construct. The schema does not support it and the engine's resolver (T03-03) is the right place for that logic.
4. **Notify.** Open an issue against T03-03 describing the overlap so the engine team can confirm the resolver handles it correctly.

### 11.3 What You MUST NOT Do

- Do not delete the parent rule.
- Do not silently lower a confidence tier to suppress an output.
- Do not edit a rule from a different jurisdiction you do not own. Coordinate with whoever drafted it.

---

## 12. Data Freshness Maintenance

Freshness scoring is owned by T02-07. The analyst owns the act of re-verifying and updating `last_verified`.

### 12.1 Re-Verification Cadence

Default cadence by confidence tier:

| Tier | Cadence |
|------|---------|
| 1 | Every 12 months |
| 2 | Every 6 months |
| 3 | Every 3 months |

Cadence may be tightened for any rule with volatile underlying regulation (e.g. a recently amended ordinance) by adding a tag `freshness:90d` or `freshness:30d` and noting the override in `reviewer_notes`.

### 12.2 Re-Verification Steps

For each rule due for review:

1. Re-open every citation URL. Confirm content still matches the cited text. Replace broken URLs with current canonical URLs and re-snapshot to Wayback.
2. Confirm any threshold values still reflect the current regulation. If the regulation has changed, treat this as a substantive update (§3.5, MAJOR or MINOR bump) and follow the full drafting workflow.
3. Confirm the form URLs and submission URLs in `outputs.forms[].url` and `outputs.submission` still resolve.
4. Update `provenance.last_verified` to today (PATCH bump).
5. Update `retrieved_at` on every refreshed citation.
6. If nothing substantive changed, commit and open a lightweight PATCH PR. Peer review is still required but the checklist is narrower (citations and `last_verified` only).

### 12.3 Freshness Alerts

T02-07 emits alerts when a rule crosses its cadence threshold or when a citation URL becomes unreachable. On alert:

- Acknowledge the alert in the analyst queue within one business day.
- Schedule the re-verification within the cadence window.
- If unreachable URLs reveal a substantive regulation change, treat as an emergency update (§10).

---

## 13. User Feedback Handling

Per AGENTS.md *User Feedback Queue*, consultant feedback is signal, not authority. The feedback queue itself lives under T08-06.

### 13.1 Workflow

1. **Triage.** When feedback enters the T08-06 queue, the assigned analyst classifies it as: (a) regulatory accuracy issue, (b) outdated link or form, (c) jurisdiction detection issue (route to GIS team, not this SOP), or (d) field observation needing analyst investigation.
2. **Investigate.** For (a), (b), or (d), the analyst re-reads the cited source and verifies independently. The consultant's report is a lead, not a citation.
3. **Decide.** Either:
   - **Confirm.** The feedback identifies a real gap. Proceed with a rule update via this SOP's standard workflow (or emergency path if §10.1 applies).
   - **Reject.** The feedback is incorrect, scoped out (e.g. requesting legal certification), or unverifiable. Document the rationale and close the feedback item with a note visible to the submitter.
4. **Document.** Either outcome is recorded against the feedback item in T08-06 with a link to any resulting rule change.

### 13.2 What Feedback Never Does

- Never auto-publishes a rule change.
- Never bypasses peer review.
- Never modifies a live rule without going through §8 publication.
- Never overrides an analyst's documented rejection unless escalated through a separate appeals process (out of scope for this SOP — owned by product ops).

### 13.3 Feedback Volume Triage

When the feedback queue accumulates, prioritize:

1. Feedback that suggests an effective rule is producing wrong outputs.
2. Feedback identifying broken URLs or dead forms (these often qualify for §10 emergency path).
3. Feedback on Tier 3 rules (lower-confidence rules benefit fastest from real-world signal).
4. Feedback on Tier 1 / Tier 2 rules requesting minor enrichment.

---

## 14. Audit and Reproducibility

Audit-readiness is a non-negotiable platform property. Every rule change carries reviewer attribution, citation, and date. Historical replay (T00-03) must be able to reproduce past consultant outputs exactly.

### 14.1 Immutable Artifacts

- Files under `rules/effective/` and `rules/archived/` are immutable in content.
- Any change to an effective rule requires a new version (§3.5) and a transition (§9.2). The old file is never edited in place.
- Benchmark fixtures under T00-06 are immutable.

### 14.2 What Audit Looks At

When an audit happens (internal or external), expect inspection of:

- `provenance.source_citations[]` — were citations real, dated, and traceable?
- `provenance.reviewer` and PR sign-off comments — was peer review performed by a non-drafter?
- Git history — was the publication move performed by a publishing analyst (RBAC)?
- Benchmark history — do historical project replays produce the same outputs they did at the time?
- Archive integrity — are superseded rules still present and unmodified?

### 14.3 Analyst Responsibilities for Audit

- Never force-push to branches that touch `rules/effective/` or `rules/archived/`.
- Never delete archived rule files.
- Never edit a rule's `effective_from` after publication (use a new version if the effective date was wrong).
- Always reference the PR URL in `reviewer_notes` for material changes.

---

## 15. What an Analyst MUST NOT Do

This is a hard list. Any item here is a stop-the-line event.

1. Publish a rule that lacks provenance (no citations, or no `last_verified`).
2. Publish a rule that lacks explainability (missing or empty `trigger_explanation`).
3. Publish a rule without an assigned `confidence_tier`.
4. Use language asserting "guaranteed compliance," "complete certainty," "final determination," or "legal compliance certification" anywhere in `trigger_explanation`, `advisories`, or `notes` that is consultant-visible.
5. Allow user feedback to bypass peer review or auto-publish.
6. Modify a rule file under `rules/effective/` or `rules/archived/` in place.
7. Self-review or self-publish a rule you drafted.
8. Check in a rule that fails schema validation.
9. Cite an AI-generated text, a third-party summary, or a blog post as the sole source for a rule.
10. Invent a `jurisdiction_id` not registered under T00-08.
11. Encode conflict-resolution branching logic inside a rule object. (Defer to T03-03.)
12. Use the emergency path (§10) without peer review.

---

## 16. Quick Reference: A Typical Day

- **New rule.** §2 source collection → §3 normalization → §4 drafting → §5 validation → §6 benchmarks → §7 peer review → §8 publication. Expect 1–3 days end-to-end for a non-trivial Tier 1 rule.
- **Minor update.** §12.2 re-verification path. PATCH bump. Narrower peer review.
- **Emergency.** §10 fast path. Same-day turnaround target. Same gates, compressed timeline.
- **Conflict suspicion.** §11. Document; defer engine logic to T03-03.
- **Freshness alert.** §12.3. Acknowledge within one business day.
- **Consultant feedback.** §13. Treat as signal, investigate, decide, document.

---

## 17. Change Control for This SOP

Changes to this SOP require:

1. PR review from at least two regulatory analysts (one of whom holds publishing authority) and one engineer.
2. Updates to any downstream tickets the change touches (e.g. T08-04 publication tooling).
3. Communication to all active analysts before the change merges.
4. Versioning of the SOP itself in the document header on material updates.

When AGENTS.md changes in a way that affects analyst workflow, this SOP MUST be reconciled before the next rule is drafted under the new policy.
