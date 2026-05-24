# Jurisdiction Ontology Model

**Ticket:** T00-02
**Status:** Draft — pending peer review per T00-09 SOP
**Owner:** Product architecture
**Source guardrails:** [`/AGENTS.md`](../../AGENTS.md) sections *Rules Engine Architecture* (jurisdiction hierarchy), *Jurisdiction Naming & Normalization*, *Geographic Scope*, *GIS Strategy*
**Related tickets:** T00-01 (Rule Object), T00-03 (Temporal Versioning), T00-08 (Canonical Naming & Alias Format), T02-01 (Jurisdiction DB Schema), T03-03 (Rule Conflict Resolver), T05-03 / T05-04 (Spatial Overlay Detection)

---

## 1. Purpose

Defines the conceptual hierarchy, override precedence, inheritance behavior, and overlap semantics for every kind of governmental or quasi-governmental jurisdiction the rules engine recognizes.

This spec is normative for:

- The shape of the jurisdiction graph that the rules engine consults during evaluation step 1 (jurisdiction match) per T00-01 §8.
- The semantics any `rule_object.jurisdiction_level` / `rule_object.jurisdiction_id` pair must satisfy (T00-01 §5.2).
- The vocabulary T00-08 will give canonical form, T02-01 will give a database schema, and T03-03 will resolve conflicts against.

A regulatory analyst MUST be able to read this document and decide, for any new rule, which jurisdiction level it belongs to and what happens when it overlaps with another rule.

## 2. Non-Goals

This spec **does not** define:

- The canonical jurisdiction ID string format, alias normalization rules, FIPS handling, or the casing/abbreviation policy for canonical names. → **T00-08**
- The relational or document database schema that stores jurisdiction records, geometries, or alias tables. → **T02-01**
- The algorithm that resolves a conflict between two rules whose jurisdictions both apply. → **T03-03**
- The GIS pipeline that detects which jurisdictions a project geometry actually touches. → **T05-03**, **T05-04**
- Federal-region overlay structure for multi-state expansion beyond Texas. The model must remain compatible (per AGENTS.md *Geographic Scope*); concrete federal regions are deferred.
- The user-facing display name policy in the consultant permit matrix. → **T07-02**

Where another ticket owns a concept, this spec uses an opaque reference. `jurisdiction_id` is treated as an opaque string whose format is owned by T00-08; this document defines what an ID *means*, not how it is *spelled*.

## 3. Conceptual Model

### 3.1 What is a jurisdiction?

A **jurisdiction** is any governmental or quasi-governmental authority whose rules a project may be required to comply with. Each jurisdiction is a node in the ontology and has:

- a permanent internal ID (opaque string; format owned by T00-08)
- a single canonical name (no abbreviations; per AGENTS.md *Jurisdiction Naming & Normalization*)
- exactly one `jurisdiction_level` from the enum below
- zero or more aliases (registry owned by T00-08)
- zero or one **structural parent** in the hierarchy (see §4)
- zero or more **applies-within** relationships to other jurisdictions (see §6)
- an active date range (jurisdictions can be created, merged, split, or dissolved)
- an optional geometry reference (owned by T02-01 and T05-03)

A rule (per T00-01) attaches to exactly one jurisdiction via `jurisdiction_id`. Multi-jurisdiction permits are modeled as multiple rules, one per jurisdiction, not as a single rule with shared ownership.

### 3.2 `jurisdiction_level` enum

The level enum is locked by AGENTS.md *Rules Engine Architecture* and mirrored in [`schemas/rule-object.schema.json`](./schemas/rule-object.schema.json):

| Level | Token | Examples (illustrative, not authoritative) |
|-------|-------|--------------------------------------------|
| Federal | `federal` | USACE, EPA, USFWS |
| State | `state` | TCEQ, TPWD, TxDOT, RRC, PUCT |
| County | `county` | Travis County, Harris County |
| Municipality | `municipality` | City of Austin, City of Houston |
| ETJ (Extraterritorial Jurisdiction) | `etj` | Austin ETJ, Houston ETJ |
| Utility District | `utility_district` | Municipal Utility Districts (MUDs), Water Control & Improvement Districts (WCIDs) |
| Drainage District | `drainage_district` | Harris County Flood Control District, county drainage districts |
| River Authority | `river_authority` | LCRA, SARA, BRA, TRA |
| Special Jurisdiction | `special` | Edwards Aquifer Authority, port authorities, groundwater conservation districts, navigation districts, regional planning bodies |

The token strings are normative and match the rule object schema enum verbatim. Adding a new level requires an AGENTS.md edit *and* a schema bump in T00-01.

### 3.3 Why these nine levels

The list is deliberately Texas-shaped:

- **ETJ** is a Texas-specific extension of municipal authority that, in practice, applies a partial subset of city rules outside city limits. Modeling it as its own level (rather than a flag on `municipality`) is necessary because ETJ rule coverage is not always equal to in-city rule coverage.
- **River authority** and **drainage district** are split from `special` because they are common enough in Texas utility/transmission corridor work to warrant first-class treatment in the engine and analyst tooling.
- **Special** is the residual bucket. Any jurisdiction that does not fit cleanly into the eight named levels uses `special` and relies on its `jurisdiction_id` for disambiguation. This bucket is intentionally heterogeneous; analysts MUST set a meaningful canonical name and document the authority type in reviewer notes.

## 4. Hierarchy

### 4.1 Structural order

Per AGENTS.md *Rules Engine Architecture*, the hierarchy order is:

```
Federal
  → State
    → County
      → Municipality
        → ETJ
          → Utility District
            → Drainage District
              → River Authority
                → Special Jurisdiction
```

The arrow `→` means **"lower in precedence-for-additive-rules and later in evaluation"**, not "geographically inside". Geography is handled separately (§6).

### 4.2 Structural parent vs. applies-within

A jurisdiction has at most one **structural parent**, defined as the jurisdiction immediately above it in the level ordering that *contains* it for purposes of inheritance:

- A county's structural parent is the state it belongs to.
- A municipality's structural parent is its primary county. (Cities that span multiple counties pick one as structural parent and the rest as **applies-within** relations; see §6.)
- An ETJ's structural parent is its associated municipality.
- Utility, drainage, river authority, and special jurisdictions usually have the state as their structural parent because they are state-chartered entities, not subordinate to a county or city even when their service area sits inside one.

Federal has no structural parent.

The **structural parent edge** is what inheritance (§5) walks. Geographic containment, which is messier, is what overlap detection (§6) walks.

### 4.3 Rule attachment

A rule attaches at exactly one level via `jurisdiction_level` and exactly one node via `jurisdiction_id`. The level on the rule MUST match the level recorded on the jurisdiction record. T00-01 §5.2 treats the ID as opaque; this spec is what makes it non-opaque to the engine.

## 5. Override Precedence

### 5.1 The core invariant

Per AGENTS.md *Rules Engine Architecture*:

> Lower jurisdictions may add requirements, override thresholds, append advisories. Lower jurisdictions MUST NOT silently delete parent requirements.

This spec calls the rule-level mechanism for overriding **explicit supersession**, and the engine-level mechanism for resolving simultaneous applicability **precedence ordering**.

### 5.2 Precedence ordering

When two rules from different levels both apply to the same project and produce conflicting outputs on the same comparable dimension (e.g. a threshold value), the **lower** level wins for additive and threshold-tightening changes. Concretely, the engine treats the level order in §4.1 as a precedence ladder running from least specific (federal) to most specific (special).

Precedence ordering applies to:

- **Threshold tightening.** A county may set a lower acreage threshold than the state. The county threshold governs the county-level rule's firing; the state-level rule still fires independently if its own threshold is met.
- **Advisory appending.** Lower jurisdictions may append advisories to a permit matrix entry.
- **Form/submission overrides.** A municipality may require a different submission portal or supplementary form for a state-issued permit. The lower jurisdiction's rule carries its own outputs; the engine surfaces both, not one in place of the other.

Precedence ordering does NOT apply to:

- **Deletion of parent requirements.** This is prohibited (§5.3).
- **Cross-level dependency claims.** A lower jurisdiction cannot mark a higher-level prerequisite as "no longer required" through `sequencing` fields. It can add prerequisites of its own.

### 5.3 The no-silent-deletion rule

A lower-level rule MUST NOT cause a higher-level rule to be omitted from the consultant's permit matrix unless the lower-level rule's record explicitly references the higher-level rule.

The only legitimate way a lower jurisdiction can remove a parent requirement is via the `supersedes` field on the lower-level rule object (T00-01 §5.4), which carries a `rule_id@version` reference. Even then, supersession across levels is reserved for cases where a higher-level authority has formally delegated permitting authority to the lower jurisdiction (e.g. an EPA-approved state permit program). T03-03 is responsible for validating that cross-level supersessions are legitimate and not silent deletions in disguise.

If the engine ever observes a lower-level rule whose effect would be to remove a higher-level rule's output without a matching `supersedes` reference, the engine MUST:

1. Keep both rules' outputs in the permit matrix.
2. Attach a `known_unknown` flag noting the apparent conflict.
3. Route the conflict to the analyst review queue (T08-06).

This is the operational expression of AGENTS.md's "MUST NOT silently delete" requirement.

### 5.4 Precedence is not severity

Precedence ordering describes *which jurisdiction's version of a number wins for its own rule*, not *which permit is more important*. All applicable permits remain in the consultant's matrix. The platform does not rank permits by severity; that is a legal judgment outside scope (per AGENTS.md *Liability Strategy*).

## 6. Inheritance Behavior

### 6.1 What is inherited

Inheritance walks the **structural parent** edge (§4.2) upward from a project's most-specific applicable jurisdiction.

For each project, the set of applicable rules is the union of:

1. Rules attached to every jurisdiction the project geographically touches (per §7 overlap detection).
2. Rules attached to every **structural ancestor** of every jurisdiction in (1).

A rule attached to Texas applies to any project anywhere in Texas; a rule attached to Travis County applies to any project in Travis County and inherits all Texas-level rules; a rule attached to City of Austin inherits Travis County rules and Texas rules; and so on.

### 6.2 What is NOT inherited

- **Sibling jurisdictions do not share rules.** A rule attached to Harris County does not apply to projects in Travis County, even though both are in Texas.
- **Applies-within edges do not carry inheritance.** When a city spans two counties, only the city's structural-parent county's rules inherit downward; the other county's rules apply only via overlap detection (§7), not via inheritance.
- **Aliases do not multiply inheritance.** A jurisdiction with three aliases inherits once, from its single structural parent. T00-08 owns alias semantics; this spec confirms aliases are name-level, not graph-level.
- **Geometry is not inherited.** The geometry of a parent jurisdiction is not the bounding geometry of its children for evaluation purposes. The GIS pipeline (T05-03) computes overlaps directly against each jurisdiction's recorded geometry.

### 6.3 Temporal inheritance

Inheritance is evaluated **at the project's evaluation date**, using whichever ancestor jurisdiction was active on that date. If a county was reorganized, split, or renamed between the project's evaluation date and today, the engine walks the historical structural-parent edge that was active on the evaluation date. T00-03 owns the temporal selection algorithm; this spec confirms that inheritance respects it.

T00-08 owns the format and storage of historical names, merger/split records, and alias-history entries. Per AGENTS.md *Jurisdiction Naming & Normalization*, analysts MUST preserve historical names and document mergers/splits; this spec assumes that information exists and is queryable.

### 6.4 Inheritance and `applicable_project_types`

Inheritance is structural, not type-aware. A state-level rule for `transmission_line` projects inherits down to every project geographically in the state, but the rule's own `applicable_project_types` filter (T00-01 §5.2) governs whether it actually fires. Inheritance produces *candidate rules*; T00-01 §8 step 3 filters them by project type.

## 7. Overlap Handling

### 7.1 Geographic overlap vs. structural inheritance

A project can be subject to multiple jurisdictions at the same level (for example, a transmission line that crosses two counties, or sits in a city that spans two counties, or runs through both an MUD and a drainage district whose service areas overlap). This is **geographic overlap**, distinct from structural inheritance (§6).

Overlap is the normal case for linear infrastructure projects, which is the MVP focus (per AGENTS.md *Primary Industry Focus*).

### 7.2 Overlap union, not overlap merge

When multiple jurisdictions at the same level apply to a project, the engine takes the **union** of their rule sets. Each jurisdiction's rules are evaluated independently. The engine does not attempt to merge two counties' rules into a synthetic combined county.

Concretely:

- If a transmission line crosses Travis County and Hays County, every Travis County rule and every Hays County rule is a candidate. They are filtered by trigger conditions and project type independently.
- If a project sits within an MUD whose boundary overlaps a drainage district, both jurisdictions' rules are candidates. Neither suppresses the other.
- If a city spans two counties, the rules from *both* counties are candidates for any project inside the city limits, even though only one of those counties is the city's structural parent.

### 7.3 Overlap with no spatial answer

For projects without a finalized shapefile or KMZ, the platform supports manual jurisdiction entry (per AGENTS.md *GIS Intake Strategy*). When jurisdictions are entered manually:

- Overlap is whatever the user enters. The engine does not infer geographic adjacency from names.
- The engine MUST surface a `known_unknown` flag indicating that jurisdiction detection was manual and may be incomplete.
- Detected overlaps from a later shapefile upload MUST be reconciled against the manual entries with the user prompted to confirm any additions or removals.

Manual-entry semantics are user-workflow concerns; the wiring lives in T06-02 and T07-02. This spec only states that the ontology is agnostic to detection source.

### 7.4 Overlap and override precedence interact

When overlap and override precedence both apply — for example, a transmission line in two counties, each of which sets a different threshold for a state-level rule — each county's override applies to its own portion of the project. The state-level rule fires once (it is one rule); the county-level threshold overrides fire as two separate rules, one per county.

The engine does not attempt to combine two counties' thresholds into a single effective threshold. The consultant sees both county-level rules in the matrix, each with its own jurisdiction context. T03-03 owns the algorithm that resolves the per-jurisdiction firing.

### 7.5 Special jurisdictions and overlap

`special` jurisdictions (Edwards Aquifer Authority, groundwater conservation districts, port authorities, etc.) overlap freely with counties, municipalities, and each other. The engine treats `special` like any other level for overlap purposes: union of rules, no merging, structural parent is typically the state.

When a `special` jurisdiction's authority is statutorily narrower than its geographic footprint (for example, an authority that regulates only groundwater within its boundary), the narrowing is encoded in the rule's `triggers` (T00-01 §5.5), not in the ontology. The ontology records *that the authority applies in this area*; the rule records *what it cares about*.

## 8. Active Dates, Mergers, and Splits

Every jurisdiction record carries an active date range. When a jurisdiction is created, dissolved, merged with another, or split:

- The original record is preserved with its `active_to` date set.
- New records are created for the resulting jurisdictions with their `active_from` dates set.
- Cross-references between the historical and current records are stored as data; format owned by T00-08, storage owned by T02-01.

The engine MUST use the jurisdiction graph as it existed on the project's evaluation date (T00-03). Historical replay (per AGENTS.md *Temporal Versioning*) requires that mergers, splits, and renames do not retroactively erase prior structure.

This spec does not define the field names, file formats, or alias-history record shapes that capture merger/split history. Those are T00-08.

## 9. Naming, Aliases, and Geographic Normalization (Cross-Ticket Deferrals)

The following are **explicitly out of scope** for this document and are owned by sibling tickets. Rules and engine components MUST reference these standards rather than redefining them:

### 9.1 Canonical naming format → T00-08

T00-08 defines:

- The string format and character set for canonical jurisdiction names.
- Whether canonical names include type suffixes (e.g. "Travis County" vs "Travis").
- The abbreviation policy (AGENTS.md mandates no abbreviations; T00-08 spells out enforcement).
- Casing, punctuation, and whitespace rules.

This spec only states that every jurisdiction has *one* canonical name and that the canonical name is the form analysts use for display and matching.

### 9.2 Alias management → T00-08

T00-08 defines:

- The alias record shape (alias string, alias type, valid date range, source).
- How alias-history is preserved across mergers, splits, and renames.
- The lookup algorithm that maps a free-text input to a canonical jurisdiction.
- Conflict handling when an alias is ambiguous between two jurisdictions.

This spec only states that aliases exist, that they are name-level (not graph-level), and that the engine resolves them via the T00-08 lookup before doing anything in this document.

### 9.3 Geographic normalization → T00-08 (with spatial pipeline in T05-03 / T05-04)

T00-08 defines:

- FIPS code handling (state, county, place, county subdivision).
- The relationship between TIGER/Line entities, agency-published boundary files, and canonical jurisdiction records.
- How analyst-entered place names are normalized to canonical jurisdictions.

T05-03 / T05-04 define the spatial pipeline that turns a project shapefile/KMZ into a list of jurisdiction IDs. This spec only states that the pipeline returns IDs valid under §3.1.

### 9.4 ID syntax → T00-08

`jurisdiction_id` is opaque in this spec and in T00-01. T00-08 defines the string format (length, character set, embedded level prefix or absence thereof, FIPS embedding, stability rules). Until T00-08 lands, examples in this document use illustrative IDs and MUST NOT be treated as normative.

## 10. Cross-Ticket Boundaries Summary

| Concern | Owner |
|---------|-------|
| Jurisdiction ID string format | T00-08 |
| Canonical name format and casing | T00-08 |
| Alias record shape, alias-history, free-text lookup | T00-08 |
| FIPS handling, TIGER alignment, geographic normalization | T00-08 |
| Merger/split record storage format | T00-08 |
| Jurisdiction database schema (tables, columns, indexes) | T02-01 |
| Geometry storage, spatial indexing | T02-01 (storage), T05-03 (pipeline) |
| Spatial overlay detection from uploaded geometry | T05-03, T05-04 |
| Rule conflict resolution algorithm | T03-03 |
| Temporal version selection at evaluation time | T00-03 |
| Rule object field shape and validation | T00-01 |
| Permit matrix display of overlapping jurisdictions | T07-02 |
| Manual jurisdiction entry UX | T06-02 |

If a future change is needed to anything in the right column, this spec does not need to change.

## 11. Verification

This is a conceptual spec; it has no JSON Schema. The acceptance criteria are:

1. **Hierarchy completeness.** The nine `jurisdiction_level` tokens in §3.2 match the enum in [`schemas/rule-object.schema.json`](./schemas/rule-object.schema.json) exactly. Any drift is a bug in one of the two documents.
2. **No-silent-deletion enforceability.** For every cross-level supersession in `rules/effective/`, T03-03's conflict resolver MUST be able to point at a `supersedes` reference. The benchmark project category "conflicting jurisdiction projects" (AGENTS.md *Benchmark Project Library*) covers this.
3. **Inheritance round-trip.** A benchmark project located in a single municipality MUST receive, in its candidate rule set, every active rule attached to the municipality, its structural-parent county, the state, and the federal level — and no rules attached to sibling counties or sibling municipalities.
4. **Overlap union.** A benchmark project crossing two counties MUST receive both counties' candidate rules, with no merging or suppression.
5. **Temporal inheritance.** A benchmark project with an evaluation date prior to a jurisdiction rename MUST inherit from the historically-named ancestor, not the current one. This requires T00-08's alias-history data to exist, so this acceptance criterion is gated on T00-08.

These criteria become executable benchmarks under T00-06 once the rule object format (T00-01) is wired into the engine (T03-02).

## 12. Change Control

Changes to this spec require:

1. PR review from at least one regulatory analyst (T00-09 SOP) and one engineer.
2. Synchronized review with T00-01 if the `jurisdiction_level` enum changes shape.
3. Synchronized review with T00-08 if the deferral boundaries in §9 move.
4. Migration note in T02-01 if the conceptual model gains or loses a node type that the database schema must represent.
