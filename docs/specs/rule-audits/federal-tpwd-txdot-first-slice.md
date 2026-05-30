# Rule audit — federal nexus + TPWD + TxDOT (first publish slice)

**Scope.** Nine drafts in `rules/draft/` covering the federal nexus (USACE §404
/ §10 / §408, USFWS ESA §7, FAA 7460-1, NEPA, FERC §7) plus TPWD project
review and TxDOT utility installation. Goal: hand a real human analyst a
prioritized, pre-vetted slate for the first publication round.

**Methodology.** Schema validation (`scripts/rules/validate_rules.py` —
all 41 drafts pass). Per-rule review of triggers, citations, advisories,
known-unknowns. Cross-checked against the three seeded benchmark projects
under `packages/benchmark-projects/benchmarks/`. Drafts were authored by a
prior research agent (provenance `reviewer: "OpenAI Deep Research"`) — every
rule needs a real human analyst to take over the `reviewer` field before
publication.

**Caveat.** This audit is an engineering review of rule shape and obvious
regulatory framing. It is **not** a substitute for a licensed Texas
regulatory specialist's review of agency guidance currency. Every rule must
pass that gate before `rules/published/`.

## Pre-publish checklist (applies to every rule in the slate)

- [ ] Replace `provenance.reviewer` placeholder with the real analyst's name
- [ ] Re-verify each citation URL is still live and authoritative (links from
      `provenance.source_citations`)
- [ ] Set `effective_from` (and optionally `effective_to`) per the publication
      SOP — `published` rules without `effective_from` do not enter
      `effective/`
- [ ] Decide whether the rule moves through `published/` first (future-dated)
      or straight to `effective/` (per AGENTS.md temporal versioning)
- [ ] Confirm `confidence_tier` against the analyst's reading of the rule
      strength
- [ ] Re-run `python scripts/checks/run_regression.py` after the move to
      confirm no benchmark regression

## Recommended publish slate (8 of 9)

| Rule | Tier | Action | Notes |
|------|------|--------|-------|
| `us-tx-usace-section-404-da-permit` | 1 | **Publish** | Most common federal nexus trigger for transmission with stream/wetland crossings. Trigger `all` of (`project.dredge_or_fill_in_waters`) + `any` of (streams, wetlands, WOTUS) double-gates — acceptable but consider relaxing to `any` since any of the downstream conditions implies dredge/fill. |
| `us-tx-usace-section-10-da-permit` | 1 | **Publish** | Navigable-waters trigger is tight. Known-unknown flags the navigability determination correctly. |
| `us-tx-usace-section-408-permission` | 1 | **Publish (consider Tier 2)** | Gates on `intersects_usace_civil_works_project` AND `alters_usace_civil_works_project`. Both inputs are upstream-detected; analyst should consider whether the rule fires as Tier 1 absent a confirmed §408 nexus, or Tier 2 pending confirmation. |
| `us-tx-usfws-esa-section-7-consultation` | 1 | **Publish** | Requires `project.federal_nexus` + `derived.may_affect_listed_species`. Solid. Known-unknown correctly surfaces NMFS for marine resources. |
| `us-tx-faa-form-7460-1-obstruction-review` | 1 | **Publish** | 200-ft AGL threshold matches 14 CFR Part 77.9. Near-airport notice-surface path covers shorter structures. |
| `us-tx-nepa-federal-environmental-review` | 1 | **Publish** | Trigger `project.federal_nexus` + `derived.major_federal_action` is correct. `source_agency: "Council on Environmental Quality"` reads oddly — the lead federal agency runs the review, not CEQ. Consider `source_agency: "Lead federal agency (per 40 CFR §1501.7)"`. |
| `us-tx-tpwd-project-review-for-wildlife-resources` | 3 | **Publish** | Tier 3 is correct — TPWD review is coordination-based, not a hard permit gate. Advisory framing is right. |
| `us-tx-txdot-utility-installation-permit` | 1 | **Publish** | 43 TAC Ch. 21 / UAR cited correctly. UIR Form 1082 reference is current. Strongest of the state rules. |

## Hold — out of scope for v1

| Rule | Action | Reason |
|------|--------|--------|
| `us-tx-ferc-natural-gas-section-7-certificate` | **Hold** | iPermit's launch focus is electric transmission. FERC §7 covers interstate natural gas pipelines (15 USC §717f). Keep as `draft` and revisit when gas/midstream is in scope. |

## Slate-level notes

**Missing rules that the slate implies but does not contain.** These belong
to the next slice, not this one — flagged so the analyst can sequence the
backlog:

- **Section 106 / NHPA cultural-resource consultation.** Distinct from THC
  Antiquities Code (which is state-lands focused). Required on every federal
  undertaking. `us-tx-thc-antiquities-code-review-and-permit.json` does not
  cover the federal §106 process.
- **USACE NWP 12 break-out.** The §404 DA permit rule covers the full DA
  pathway. NWP 12 (Utility Line Activities, 87 Fed. Reg. 7,879) is the
  high-volume case for transmission — splitting it out would make the matrix
  more actionable.
- **FAA Part 77 obstruction marking & lighting** (separate from the 7460-1
  notice).
- **TPWD §86 sand/gravel/marl removal** for in-channel work — separate
  permit, not coordination.

**Cross-cutting input contract.** The federal slate relies on derived inputs
that today are user-supplied (`project.federal_nexus`,
`derived.may_affect_listed_species`, `derived.major_federal_action`,
`derived.near_airport_notice_surface`). Each of those needs an analyst-owned
definition or upstream detection rule. Recommend the analyst SOP capture how
intake forms / GIS detection populate them.

**Benchmark coverage of the slate.** The three seeded benchmarks
(`federal-nexus-transmission-stream-crossing`,
`known-unknown-tpwd-rare-species-overlap`,
`simple-linear-roadside-utility-txdot-row`) cover §404, USFWS §7, NEPA, TPWD,
and TxDOT. **Uncovered by current benchmarks**: USACE §10, §408, FAA 7460-1.
One new benchmark
(`tall-transmission-navigable-water-near-airport.yaml`) is added in this PR
to exercise the gap.

## Suggested publication order

1. **TxDOT utility installation** — the cleanest rule, simplest validation
   path, single-state authority.
2. **USACE §404, §10, §408** as a federal-waters batch — they're frequently
   triggered together.
3. **USFWS §7 + NEPA** as a federal-process batch — both gate on
   `project.federal_nexus`.
4. **FAA 7460-1** — solo, applies to projects with `structure_height_ft_agl > 200`.
5. **TPWD project review** — last, because it's coordination (Tier 3) and
   benefits from the federal rules being live first so its advisory framing
   reads correctly.

## After publish

- Move the rules from `rules/draft/` to `rules/published/` (or directly to
  `rules/effective/` if `effective_from` ≤ today) via the publication
  workflow (S05-02 — author drafts, reviewer publishes; separation of
  duties enforced in code).
- Re-run `python scripts/checks/run_regression.py` and the new benchmark.
- Tag the ruleset snapshot so consultant matrices can pin to it
  (`ruleset_version.content_hash`).
- Update `rules/README.md` — remove "Scaffold only" once the first slate is
  effective.
