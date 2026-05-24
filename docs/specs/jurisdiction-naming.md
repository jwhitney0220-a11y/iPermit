# Jurisdiction Naming & Normalization Standard

**Ticket:** T00-08
**Status:** Draft — pending peer review per T00-09 SOP
**Owner:** Regulatory architecture
**Source guardrails:** [`/AGENTS.md`](../../AGENTS.md) sections *Jurisdiction Naming & Normalization*, *Rules Engine Architecture*, *Geographic Scope*, *GIS Strategy*
**Related tickets:** T00-01 (Rule Object), T00-02 (Jurisdiction Ontology), T00-03 (Temporal Versioning), T02-01 (Jurisdiction DB), T02-06 (Alias-Driven Ingest Matching), T05-01 / T05-02 (Geometry Store), T05-03 (Spatial Detection)

---

## 1. Purpose

Defines the **canonical record shape** for every jurisdiction the iPermit platform recognizes: how its permanent ID is spelled, how its canonical name is written, how its aliases are recorded, how its parent is referenced, how FIPS codes are attached, how its geometry is pointed at, and how its lifecycle (creation, merger, split, dissolution) is captured.

The schema in this document is the **canonical jurisdiction data shape**. T00-02 (Ontology) refers to this schema for record shape; T02-01 (Database) implements it; T02-06 (Ingest Matching) consumes it.

This standard is normative for any jurisdiction record written to `packages/jurisdiction-models/` (per AGENTS.md *Repository Strategy*) and for the `jurisdiction_id` opaque string referenced by [`rule-object.md`](./rule-object.md) §5.2.

## 2. Non-Goals

This spec **does not** define:

- The conceptual ontology (hierarchy, override behavior, inheritance, overlap semantics). → **T00-02**
- The database schema, indexes, or storage engine for jurisdiction records. → **T02-01**
- The GIS storage format, spatial index, or geometry record schema. → **T05-01**, **T05-02**
- The shapefile/KMZ ingest pipeline that detects which jurisdiction IDs apply to a project geometry. → **T05-03**
- The free-text alias matching algorithm used during regulatory document ingest. → **T02-06**
- The rule object shape itself. → **T00-01**
- Federal regional structure beyond what is required to seat U.S. records at the root.

Where another ticket owns a downstream concern, this spec is the *upstream* — the data shape those tickets must consume.

## 3. Internal ID Format

### 3.1 Design principles

A `jurisdiction_id` MUST be:

1. **Permanent.** Once issued, never reused. An ID identifies a jurisdiction record across all time, even after the jurisdiction is dissolved.
2. **Opaque to consumers.** Other specs (T00-01, T00-02) treat the ID as an opaque string. The structure described here is for analyst readability and tooling, not for runtime parsing.
3. **Hierarchical and self-describing.** A human reader should be able to tell the country, state, and level from the ID alone. This is convenience, not contract.
4. **Slug-safe.** Lowercase ASCII, kebab-case. No spaces, no punctuation, no Unicode. Safe in URLs, filenames, git paths, and database keys without escaping.
5. **Stable under canonical-name change.** A municipality that renames does NOT get a new ID; only mergers and splits create new IDs (§8).

### 3.2 Formal grammar

The ID is built from path segments joined by `-`. The grammar in extended BNF:

```
jurisdiction_id   ::= country
                    | country "-" state
                    | country "-" state "-" level "-" name_segments

country           ::= [a-z]{2}                       ; ISO 3166-1 alpha-2, lowercase. "us" for MVP.
state             ::= [a-z]{2}                       ; ISO 3166-2 subdivision suffix, lowercase. "tx" for Texas.
level             ::= "federal"
                    | "state"
                    | "county"
                    | "municipality"
                    | "etj"
                    | "utility-district"
                    | "drainage-district"
                    | "river-authority"
                    | "special"

name_segments     ::= name_segment ("-" name_segment)*
name_segment      ::= [a-z0-9]+                      ; lowercase alphanumerics; no underscores, no hyphens inside.
```

The equivalent regular expression (also enforced by the JSON Schema in §11):

```
^[a-z]{2}(-[a-z]{2})?(-(federal|state|county|municipality|etj|utility-district|drainage-district|river-authority|special)-[a-z0-9]+(-[a-z0-9]+)*)?$
```

### 3.3 Note on `level` token spelling

The `level` segment in the ID uses **kebab-case** (e.g. `utility-district`, `river-authority`) because the ID itself is a single kebab-case slug. The `jurisdiction_level` enum *value* uses **snake_case** (e.g. `utility_district`, `river_authority`) because it mirrors [`rule-object.schema.json`](./schemas/rule-object.schema.json) which is fixed by T00-01.

This is intentional. A record's `jurisdiction_level: river_authority` corresponds to an ID containing `-river-authority-`. The translation is a literal `_` ↔ `-` swap; tooling that needs to derive one from the other does so with a single substitution.

### 3.4 Canonical examples

| ID | Meaning |
|----|---------|
| `us` | United States, federal root. The only valid `federal`-level country record. |
| `us-tx` | State of Texas. |
| `us-tx-county-travis` | Travis County, Texas. |
| `us-tx-municipality-austin` | City of Austin. |
| `us-tx-etj-austin` | City of Austin Extraterritorial Jurisdiction. |
| `us-tx-river-authority-lcra` | Lower Colorado River Authority. |
| `us-tx-utility-district-northtown-mud` | Northtown Municipal Utility District. |
| `us-tx-drainage-district-harris-county-flood-control` | Harris County Flood Control District (drainage district, not the county itself). |
| `us-tx-special-edwards-aquifer-authority` | Edwards Aquifer Authority. |

### 3.5 Why slugs and not surrogate keys

A database surrogate (e.g. a UUID) would also satisfy the permanence and opacity requirements. We use readable slugs instead because:

- Analyst review of rule files in git diffs is a primary workflow (AGENTS.md *Rules Engine Architecture*: rules MUST be human-readable). Diffs that say `us-tx-county-travis` are reviewable; diffs that say `7f3e91...` are not.
- Slugs survive export to CSV/YAML/Markdown without secondary lookup.
- Permanence is enforced by policy (§3.1) and by the merger/split rules (§8), not by the choice of identifier type.

### 3.6 Slug never reused

Once a record exists with a given `jurisdiction_id`, that string is permanently retired even if the jurisdiction is dissolved. A new jurisdiction at the same place with the same name (rare but possible — e.g. a dissolved MUD's territory absorbed into a new MUD with the same name) gets a new ID. T00-02 §6.3 confirms aliases are name-level, not ID-level, so reusing an ID would corrupt historical replay.

## 4. Canonical Name

### 4.1 Format rules

A `canonical_name` MUST:

1. Be the **full official name** the jurisdiction itself publishes. No abbreviations even if the abbreviation is widely used. "Travis County", not "Travis Co." "Lower Colorado River Authority", not "LCRA".
2. Use **Title Case** for English-language names. Each significant word capitalized; minor conjunctions and prepositions lowercase except at the start ("City of Austin", "Edwards Aquifer Authority", "Brazos River Authority of Texas").
3. Be **UTF-8** encoded.
4. **Preserve diacritics** as they appear in the official record. A canonical name containing `ñ`, `é`, or any non-ASCII character is stored as-is (e.g. a hypothetical "Cañada del Río Water District" would store `Cañada`, not `Canada`). ASCII-folded forms are recorded as `colloquial` aliases (§5).
5. Use the **right single quotation mark** `U+2019` (`’`) for apostrophes, never the ASCII apostrophe `U+0027` (`'`). Example: "St. Stephen’s Community Improvement District", not "St. Stephen's...". Ingest tooling MUST normalize ASCII apostrophes in source data to `U+2019` when constructing canonical names.
6. Avoid **trailing or leading whitespace**. Internal whitespace is a single ASCII space.
7. Include **type suffix** when the official name does (e.g. "Travis County" includes "County"; "City of Austin" includes "City of"; "Lower Colorado River Authority" includes "Authority"). Do not strip type words even if they seem redundant with `jurisdiction_level`.

### 4.2 Abbreviation prohibition

Per AGENTS.md *Jurisdiction Naming & Normalization*: "Analysts MUST avoid abbreviations in canonical names." This applies to:

- Type abbreviations: `Co.`, `Cnty`, `Twp`, `MUD`, `WCID`, `ETJ`, `RA`, etc. The full forms — County, Township, Municipal Utility District, Water Control and Improvement District, Extraterritorial Jurisdiction, River Authority — go in the canonical name.
- Honorific or compass abbreviations inside place names: `St.`, `N.`, `W.`. Spell out as `Saint` (or whatever the official form uses), `North`, `West` — unless the official record itself uses the abbreviation (e.g. some Texas places officially spell themselves with `St.`; defer to the official record).
- Initialisms used in everyday speech: `LCRA`, `BRA`, `SARA`. These go in the `aliases` array with `alias_type: abbreviation`.

When the official record itself disagrees about its name (e.g. its enabling statute uses one form and its website another), the analyst MUST pick the most authoritative source (statute > agency-published official name > website > directory), record the chosen form as canonical, and record the alternates as colloquial aliases with their sources.

### 4.3 Canonical name is mutable; ID is not

A jurisdiction that changes its official name keeps the same `jurisdiction_id`. The old name becomes a historical alias (§5.2) with a `date_to` set to the rename effective date and a new alias entry MAY be created if interim transitional names existed. The new official name replaces `canonical_name`.

This is distinct from merger/split (§8), where the ID itself retires.

## 5. Aliases

### 5.1 Why aliases are a first-class concept

Source documents that analysts ingest (statutes, ordinances, agency forms, consultant intake submissions, GIS attribute tables) use a wide variety of forms for the same jurisdiction. Reliable rule attribution and free-text matching during ingest (T02-06) require a structured record of every alternate name observed in the wild.

### 5.2 Alias record shape

Each entry in the `aliases` array is an object:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `value` | string | yes | The alternate string exactly as observed. Preserve original casing and punctuation. |
| `alias_type` | enum | yes | One of: `abbreviation`, `historical`, `colloquial`, `misspelling`. |
| `source` | string | no | Where the alias was observed (URL, statute citation, intake form ID, agency document). Strongly recommended; T02-06 weights matches by source quality. |
| `date_from` | date | no | First date this alias was in use. Required pattern for `historical`; meaningless for other types. |
| `date_to` | date | no | Last date this alias was in use. Null/absent means still current. |
| `notes` | string | no | Free-text analyst context. |

`alias_type` semantics:

- `abbreviation` — an initialism or shortened form the jurisdiction itself or its consumers commonly use. Examples: `LCRA`, `Travis Co.`, `COA ETJ`.
- `historical` — a former official name. Carries `date_from` and `date_to` covering its period of use. Example: `Waterloo` for the City of Austin (1837–1839).
- `colloquial` — an informal long-form variation that is not strictly an abbreviation and not a misspelling. Examples: `Travis County, TX`; `Lower Colorado River Authority of Texas`; an ASCII-folded variant of a diacritic-bearing canonical name.
- `misspelling` — a recurrent erroneous spelling observed in source documents. Recording misspellings lets ingest tooling normalize them without lowering confidence on the underlying match. Example: `Travis Cnty`.

### 5.3 Uniqueness and ambiguity

The `aliases` array MUST contain no duplicate `value` strings within a single record (schema enforces `uniqueItems`). Across records, two jurisdictions MAY legitimately share an alias string (e.g. `Austin` could refer to City of Austin or to Austin County, TX) — disambiguation is T02-06's responsibility, and the analyst MUST record source metadata that makes disambiguation possible.

### 5.4 Alias history is preserved on rename and merger

When a canonical name changes:

- The old `canonical_name` becomes a `historical` alias on the same record, with `date_to` set to the day before the new name took effect.
- The new canonical name does NOT need to appear in aliases (it lives in `canonical_name`).

When a jurisdiction is merged or split (§8):

- The old record retains its full alias history. The old `canonical_name` is preserved on the old record, not migrated to the new record.
- The new record(s) start with their own canonical name and aliases. The old jurisdiction's name MAY appear as a `historical` alias on a new record only if the new jurisdiction is, by official statute, considered a renaming or continuation. Otherwise the link between old and new lives in `replaced_by` / `replaced_from`.

## 6. Parent Jurisdiction

### 6.1 The parent edge

Every non-federal record MUST set `parent_jurisdiction_id` to the ID of its **immediate structural parent** per T00-02 §4.2. Federal records (those with `jurisdiction_level: federal`) MUST set `parent_jurisdiction_id` to `null`.

- County → State.
- Municipality → primary County (when the municipality spans multiple counties, the primary is the one in which the municipal hall sits, or the one designated by enabling charter — analyst judgment, documented in `notes`).
- ETJ → its associated Municipality.
- Utility District, Drainage District, River Authority, Special → State (they are state-chartered entities, not subordinate to a county or city, even when their service area sits inside one).

### 6.2 Single parent only

A jurisdiction record MUST have exactly one parent (or null for federal). **Multi-parent jurisdictions are explicitly disallowed by this standard.**

The cases that might tempt a multi-parent model — an ETJ that straddles two cities, a special district that crosses two states, a transmission corridor falling inside two counties — are modeled as follows:

- An ETJ that straddles two municipalities is **two separate jurisdiction records**, each with its own parent municipality and its own geometry that covers only the portion attributable to that municipality. The fact that they geographically abut is captured in the geometry store (T05-01), not in the jurisdiction graph.
- A district whose service area crosses a state line is **two records**, one per state. The cross-state coordination is a rule-level concern, not a record-level one.
- A project crossing two counties is **not** a jurisdiction problem — it's an overlap problem handled by T00-02 §7 (overlap union) and T05-03 (spatial detection). The county records themselves remain single-parent.

This constraint keeps inheritance (T00-02 §6) walkable as a tree and keeps the schema validatable without graph-cycle detection.

### 6.3 Parent reference validity

The parent ID MUST resolve to an existing record whose `active_from`/`active_to` range overlaps the child's `active_from`/`active_to` range. T02-01 enforces referential integrity at the database level; this spec mandates the constraint.

A child record's `active_from` MUST be on or after its parent's `active_from`. A child's `active_to`, if set, MUST be on or before its parent's `active_to` *unless* the parent has been merged/split into successors that cover the child's lifetime (in which case the chain of `replaced_by` carries the inheritance).

## 7. FIPS Codes

### 7.1 What FIPS we record

`fips` is an object (not a flat string) carrying up to three sub-fields, all string-typed to preserve leading zeros:

| Sub-field | Pattern | When required |
|-----------|---------|---------------|
| `fips_state` | `^[0-9]{2}$` | Required for federal, state, and county records. |
| `fips_county` | `^[0-9]{5}$` | Required for county records (encoded as state + county; Travis County is `48453`). |
| `fips_place` | `^[0-9]{7}$` | Optional, used for municipalities (encoded as state + place; City of Austin is `4805000`). |

### 7.2 Required vs. optional

| Level | `fips_state` | `fips_county` | `fips_place` |
|-------|--------------|---------------|--------------|
| `federal` | required (`00` reserved for U.S. root) | not applicable | not applicable |
| `state` | required | not applicable | not applicable |
| `county` | required | required | not applicable |
| `municipality` | recommended | not applicable | optional |
| `etj` | optional | not applicable | optional (inherited from parent municipality where applicable) |
| `utility_district`, `drainage_district`, `river_authority`, `special` | optional | not applicable | optional |

Sub-county jurisdictions (utility districts, drainage districts, river authorities, special) generally do not have a FIPS code at all, because the FIPS system does not enumerate them. For these, the `fips` object MAY be omitted entirely.

### 7.3 Leading zeros and string typing

FIPS codes have semantically significant leading zeros (e.g. Alabama is FIPS state `01`, not `1`). All FIPS sub-fields are typed as `string` in the schema and MUST be written with their leading zeros preserved. Integer typing is prohibited.

### 7.4 FIPS is identification, not boundary

FIPS codes identify a jurisdiction; they do not store its boundary geometry. Boundary data lives in the geometry store (§9). The pairing of FIPS code and geometry is the responsibility of T05-02, which reconciles Census TIGER/Line boundaries with agency-published boundary files where they disagree.

## 8. Active Dates, Mergers, and Splits

### 8.1 Active date range

Every record carries:

- `active_from` (date, required) — the date the jurisdiction came into legal existence (incorporation, county formation, district creation, federal authorization). For pre-1900 records where the exact day is uncertain, an analyst-attested approximate date is acceptable; the source and any uncertainty MUST be captured in `notes`.
- `active_to` (date or null) — the date the jurisdiction ceased to exist. Null means currently active.

`active_to`, when set, MUST be strictly after `active_from`. The validator in §10 enforces this.

A rule attached to a jurisdiction is only candidate-applicable on dates within `[active_from, active_to]`. T00-03 owns the temporal selection algorithm; this spec owns the dates the algorithm reads.

### 8.2 Merger

When two or more jurisdictions are merged into one:

1. **Create a new record** for the merged entity with a new `jurisdiction_id`, its own `canonical_name`, and `active_from` set to the merger effective date.
2. The new record's `replaced_from` array contains the IDs of every predecessor.
3. Each **predecessor record** is updated: `active_to` set to the day before the merger effective date, and `replaced_by` array updated to contain the single new ID.
4. Predecessor `canonical_name` and `aliases` are preserved as historical record. Do NOT delete predecessor records.

### 8.3 Split

When one jurisdiction is split into two or more:

1. **Create new records** for each successor, each with a fresh `jurisdiction_id`, its own `canonical_name`, and `active_from` set to the split effective date.
2. Each new record's `replaced_from` array contains the single ID of the original.
3. The **original record** is updated: `active_to` set to the day before the split effective date, and `replaced_by` array updated to contain all successor IDs.
4. The original record is preserved; its rules remain attached and remain queryable for evaluation dates inside its active range.

### 8.4 Dissolution

A jurisdiction that is dissolved with no successor:

- `active_to` is set to the dissolution date.
- `replaced_by` is left empty (or omitted).
- The record is preserved.

### 8.5 Rename without merger or split

A rename is **not** a merger or split. The record keeps its `jurisdiction_id`, the new name replaces `canonical_name`, and the old name becomes a `historical` alias (§5.4). `active_from`/`active_to` are unchanged.

### 8.6 Why this asymmetry

Mergers and splits change the **identity** of the jurisdiction in a way that materially affects rule attribution: a rule attached to a merged predecessor must not silently apply to its successor without analyst review, because the legal authority that issued the rule no longer exists in the same form. Forcing a new ID forces that review. Renames change only the label; rule attribution is unaffected.

## 9. Geometry Reference

`geometry_ref` is an **opaque string pointer** to a geometry record in the GIS store. It MUST NOT contain inline GeoJSON, WKT, coordinates, or any geometric data. The full GIS schema is T05-01's concern.

The pointer format is not specified by this standard beyond being a non-empty UTF-8 string ≤ 200 characters. Recommended convention, illustrative only: `geom:<jurisdiction-slug>:<source>-<vintage>` (e.g. `geom:tx-county-travis:tiger-2024`). The actual format is fixed by T05-01.

`geometry_ref` MAY be null when:

- The jurisdiction has no spatial extent (a placeholder root like `us`).
- The geometry has not yet been ingested. Records may exist before their geometry does; ingest order is not coupled.

When `geometry_ref` is null, the jurisdiction is invisible to T05-03's spatial detection pipeline and rules attached to it can only fire via manual jurisdiction entry (AGENTS.md *GIS Intake Strategy*).

## 10. Validation Rules

A jurisdiction record is **valid** if and only if all of the following hold:

1. **ID grammar.** `jurisdiction_id` matches the regex in §3.2.
2. **Required fields.** `jurisdiction_id`, `canonical_name`, `jurisdiction_level`, `active_from` are present. `parent_jurisdiction_id` is present (possibly null) and is null iff `jurisdiction_level` is `federal`.
3. **Parent resolves.** If `parent_jurisdiction_id` is non-null, a record with that ID exists in the registry.
4. **Parent temporal overlap.** The parent record's active range covers this record's active range (with successor-chain allowance per §6.3).
5. **Active range ordering.** If `active_to` is non-null, `active_to > active_from`.
6. **Replaced references resolve.** Every ID in `replaced_by` and `replaced_from` exists in the registry.
7. **Merger/split temporal consistency.** When `replaced_by` is set, `active_to` is set; when `replaced_from` is set, `active_from` is the same date for every record that shares the same `replaced_from` (split case) or the merger effective date (merger case).
8. **FIPS requirements per §7.2.**
9. **Alias uniqueness.** No two alias entries within a single record share the same `value` string.
10. **Canonical name format per §4.** (Cannot be schema-enforced in full; rule (10) is reviewed by analysts at publication time.)

Constraints 1, 2, 5, 8, and 9 are enforced by the JSON Schema in §11. Constraints 3, 4, 6, and 7 require cross-record validation and are enforced by the registry loader (T02-01). Constraint 10 is review-gated under T00-09.

## 11. JSON Schema and Examples

Machine-readable schema: [`schemas/jurisdiction-record.schema.json`](./schemas/jurisdiction-record.schema.json) — JSON Schema draft 2020-12.

Reference examples: [`examples/jurisdiction-record-examples.json`](./examples/jurisdiction-record-examples.json) and [`examples/jurisdiction-record-examples.yaml`](./examples/jurisdiction-record-examples.yaml) (same content in both formats). Four records are included spanning multiple levels: a Texas county (Travis), a municipality (City of Austin), an ETJ (Austin ETJ), and a river authority (LCRA).

Validate the examples locally:

```bash
python3 -c "
import json, jsonschema
schema = json.load(open('docs/specs/schemas/jurisdiction-record.schema.json'))
examples = json.load(open('docs/specs/examples/jurisdiction-record-examples.json'))
v = jsonschema.Draft202012Validator(schema)
for ex in examples:
    errors = list(v.iter_errors(ex))
    print('VALID' if not errors else 'INVALID', ex['jurisdiction_id'])
"
```

This validation is wired into CI under T01-07.

## 12. Texas-Specific Guidance

Per AGENTS.md *Geographic Scope*, MVP geography is Texas only. The standard above is state-scalable, but the following Texas-specific facts MUST be observed when seeding the initial registry.

### 12.1 Texas FIPS

- `fips_state` for Texas is `48`. Every Texas county FIPS code begins with `48` (e.g. Travis `48453`, Harris `48201`, Bexar `48029`).
- Texas has **254 counties**, the most of any U.S. state. The seeding playbook (T02-01 / AGENTS.md *Initial Dataset Seeding*) must enumerate all 254 with FIPS codes.
- Texas FIPS place codes are seven digits (state `48` + five-digit place code; e.g. Austin `4805000`).

### 12.2 Texas ETJ

ETJ in Texas is governed by **Texas Local Government Code Chapter 42**. Key facts the seeding effort MUST respect:

- ETJ size is statutorily tied to municipal population (§42.021), creating a ½-mile to 5-mile ring depending on city size.
- ETJ scope was materially affected by **S.B. 2038 (88th Legislature, 2023)**, which allows landowner-initiated release of certain tracts from a municipality's ETJ. Released tracts remain geographically where they always were but are no longer subject to ETJ rules.
- iPermit models S.B. 2038 releases as **geometry changes** on the ETJ record, not as multi-parent jurisdictions or as separate records per §6.2.
- Each Texas city's ETJ is one jurisdiction record (e.g. `us-tx-etj-austin`), with the municipality as structural parent.

### 12.3 Texas river authorities

Texas has multiple major river authorities created by state statute under Article XVI §59 of the Texas Constitution (Conservation Amendment). Examples that the MVP seeding must include:

- `us-tx-river-authority-lcra` — Lower Colorado River Authority (created 1934).
- `us-tx-river-authority-bra` — Brazos River Authority (created 1929).
- `us-tx-river-authority-sara` — San Antonio River Authority (created 1937).
- `us-tx-river-authority-tra` — Trinity River Authority of Texas (created 1955).

Each has the state as structural parent (`us-tx`), not any county. Each carries the full canonical name; the four-letter initialisms (LCRA, BRA, SARA, TRA) go in `aliases` with `alias_type: abbreviation`.

### 12.4 Texas utility districts

Texas utility districts include Municipal Utility Districts (MUDs), Water Control and Improvement Districts (WCIDs), Public Utility Districts (PUDs), and others. They are created under various chapters of the Texas Water Code and Local Government Code, and their structural parent is the state (`us-tx`), not the county whose territory they sit in — they are state-chartered districts.

ID convention: `us-tx-utility-district-<district-slug>`. Canonical names spell out the type ("Northtown Municipal Utility District", not "Northtown MUD"). The MUD/WCID/PUD initialism goes in `aliases`.

There are several thousand utility districts in Texas. The seeding playbook is responsible for prioritization; this standard only governs how each one is recorded.

### 12.5 Texas special jurisdictions

Authorities like the Edwards Aquifer Authority, port authorities, navigation districts, and groundwater conservation districts use `jurisdiction_level: special`. Examples:

- `us-tx-special-edwards-aquifer-authority` — Edwards Aquifer Authority (1993).
- `us-tx-special-port-of-houston-authority` — Port of Houston Authority.

The `special` bucket is intentionally heterogeneous (T00-02 §3.3). The analyst MUST set a meaningful canonical name and document the authority type in reviewer `notes` so downstream consumers can disambiguate.

## 13. Cross-Ticket Boundaries

| Concern | Owner |
|---------|-------|
| Conceptual hierarchy, override behavior, inheritance, overlap | T00-02 |
| Jurisdiction database schema, indexes, referential integrity enforcement | T02-01 |
| Geometry storage and the geometry record schema | T05-01 |
| TIGER/Line reconciliation and agency-published boundary alignment | T05-02 |
| Spatial overlay detection from shapefile/KMZ | T05-03 |
| Alias-driven free-text matching during ingest | T02-06 |
| Temporal version selection at evaluation time | T00-03 |
| Rule object field shape | T00-01 |
| Permit matrix display of canonical names and aliases | T07-02 |
| Manual jurisdiction entry UX | T06-02 |

If a future change is needed to anything in the right column, this spec does not need to change. Conversely, changes to canonical naming, ID grammar, alias structure, FIPS handling, or merger/split semantics require a coordinated PR here.

## 14. Change Control

Changes to this spec require:

1. PR review from at least one regulatory analyst (T00-09 SOP) and one engineer.
2. Schema bump if the JSON Schema changes shape: `schemas/jurisdiction-record.schema.json` carries a `$id` URL versioned by date — bump it on breaking changes.
3. Synchronized review with T00-01 if the `jurisdiction_level` enum changes shape (the rule object schema and this schema share the enum).
4. Synchronized review with T00-02 if the cross-ticket deferral boundaries in §13 move.
5. Migration plan for existing jurisdiction records if any required field is added, removed, or has its semantics changed.
