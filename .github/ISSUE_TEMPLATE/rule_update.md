---
name: Regulatory rule add/change
about: Request a new permit rule, or a change to an existing one (routes to the analyst review queue — does not auto-publish)
title: "[Rule] "
labels: ["rule-update", "analyst-queue"]
assignees: []
---

<!--
This template is for regulatory data: new permits, changed triggers/thresholds,
updated forms, citations, or jurisdictions. It is NOT a code bug — for engine or
UI defects use the Bug report template.

IMPORTANT: This request enters the regulatory analyst review queue (T08-06,
analyst SOP T00-09 §13). It does NOT auto-publish. No rule reaches consultants
until a drafting analyst verifies the source, a non-drafting analyst peer-reviews
it, and a publishing analyst approves it (SOP §1, §7, §8). Consultant feedback is
treated as a lead for analyst investigation, never as authoritative input
(AGENTS.md *User Feedback Queue*).
-->

## Request type

- [ ] New permit rule
- [ ] Change to an existing rule (trigger, threshold, output, form, citation)
- [ ] Outdated form or submission link
- [ ] Suspected jurisdiction conflict
- [ ] Field-observed regulatory change

## Permit / rule

<!-- Permit name and permit code if known. If editing an existing rule, give its rule_id. -->

- Existing `rule_id` (if any):
- Permit name:

## Jurisdiction (required)

<!--
Which jurisdiction governs this? Use the canonical name (T00-08), not an
abbreviation. Give the jurisdiction level (Federal / State / County / Municipality
/ ETJ / Utility District / Drainage District / River Authority / Special) and the
source agency.
-->

- Jurisdiction level:
- Canonical jurisdiction name:
- Source agency:

## Source citation (required)

<!--
A request without an authoritative source cannot be drafted (SOP §2). Provide at
least one source from the authority hierarchy: statute > regulation > agency
rulemaking > agency guidance > agency website > form. Consultant feedback, blogs,
and third-party summaries are never the sole citation.

For each source give: the full URL, a formal legal-style reference, and (if you
can) a Wayback snapshot. Paste the exact sentence(s) that establish the trigger.
-->

- Full URL(s):
- Formal reference (e.g. `30 TAC § 305.541`, `33 U.S.C. § 1344(a)`):
- Relevant excerpt (quote the trigger/requirement text):

## Confidence tier (required)

<!--
Your suggested tier per AGENTS.md *Permit Confidence Tiers* / SOP §2.4. The
analyst makes the final call; if unsure between two tiers, suggest the lower one.
-->

- [ ] Tier 1 — statutory/regulatory, uniform, unambiguous threshold, stable interpretation
- [ ] Tier 2 — supported but local implementation varies
- [ ] Tier 3 — informational only; consultant confirmation required (must carry known unknowns)

## Trigger / threshold

<!-- When should this permit fire? Project types, thresholds, spatial overlays, dependencies. -->

## Known unknowns

<!-- What is uncertain or unverified? Tier 3 requests must fill this in. -->

## Impact

- Affected project types:
- Is an existing effective rule producing a wrong output today? [ ] yes  [ ] no

---

<!--
What happens next (informational):
1. Triage and classification into the analyst queue (SOP §13.1).
2. A drafting analyst independently verifies the source and drafts/edits the rule
   in `rules/draft/` on an `analyst/<rule-id>-<version>` branch (SOP §4).
3. Schema validation against rule-object.schema.json and benchmark tests (SOP §4.5, §6).
4. Non-drafting analyst peer review (SOP §7), then publishing-analyst approval (SOP §8).
This issue is closed with a link to the resulting rule change, or with a documented
rejection rationale (SOP §13.1).
-->
