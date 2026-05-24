# Explainability & Traceability Standards

**Ticket:** T00-05
**Status:** Draft — pending peer review per T00-09 SOP
**Owner:** Product architecture
**Source guardrails:** [`/AGENTS.md`](../../AGENTS.md) sections *Liability Strategy*, *Permit Confidence Tiers*, *Technical Philosophy*, *Rule Object Specification*, *Data Governance*
**Related tickets:** T00-01 (Rule Object, merged), T00-02 (Jurisdiction Ontology), T00-03 (Temporal Versioning & Ruleset Snapshots), T00-04 (Dependency & Sequencing), T00-06 (Benchmark Library), T01-04 (Audit Log Persistence), T02-07 (Data Freshness Scoring), T03-05 (Engine Implementation), T07-02 (Permit Matrix UI)

---

## 1. Purpose & Audience

Every permit the deterministic rules engine surfaces — fired or short-circuited — MUST carry a structured **permit explanation record**. The explanation record is the audit-grade artifact that lets a consultant, a reviewing analyst, or a litigant reproduce *why* the engine reached that conclusion at that moment in time.

Explainability is priority #2 in the iPermit *Technical Philosophy* (AGENTS.md), and traceability is priority #3. This spec is normative for any engine output a consultant or auditor consumes.

Audiences and what they need from a record:

| Audience | Need |
|----------|------|
| Consultant (everyday user) | Plain-language *why* this permit, *what threshold* triggered it, what additional review is needed. |
| Reviewing analyst | Full trigger path, citations, ruleset version, and reproducibility keys for QA. |
| Litigant / external auditor | Byte-identical replay of the same record given the same inputs + same ruleset version + same evaluation date. |
| Regression test (T00-06) | Diff a benchmark project's recorded record against the live engine's output. |

This spec defines the **shape of the record**, the **required content**, and the **reproducibility contract**. It does *not* define UI rendering (T07-02), audit log persistence (T01-04), or the engine internals (T03-05).

## 2. Non-Goals

This spec does **not** define:

- Rule object field shapes — owned by T00-01 (merged).
- Ruleset snapshotting, content-hash algorithm, or temporal selection — owned by T00-03. This spec uses an opaque `content_hash` string.
- Engine evaluation algorithm or short-circuit implementation — owned by T03-05. This spec only defines what the engine MUST emit.
- Permit matrix UI layout, badge colors, or tooltip behavior — owned by T07-02. This spec defines plain-text fields and tier integers; UI maps them.
- Audit log storage, retention, or query API — owned by T01-04. This spec defines a record; the audit log persists records.
- Negative-explanation triggering policy (always emit vs on-demand) — implementation detail of T03-05 and the consultant UI.

## 3. Design Principles

A permit explanation record MUST:

1. **Be self-contained.** A reader with the record alone (no engine, no DB) can understand the decision. Citations and advisory text are embedded, not referenced by ID.
2. **Be declarative.** The record describes outcomes, not procedure. No execution traces, no stack frames, no internal IDs that aren't part of the public ontology.
3. **Be deterministic.** Given the same inputs and ruleset, two runs produce byte-identical records (§6).
4. **Be AGENTS.md-compliant in language.** Every record carries at least one advisory; no record uses prohibited certainty language.
5. **Be source-traceable.** Every fired record cites at least one authoritative source, copied verbatim from the rule's `provenance.source_citations`.
6. **Be jurisdictionally honest.** The full applicable jurisdiction chain is recorded, not just the rule's own level. A federal rule that fired for a Texas county project records the chain `federal → state → county`.

A record MUST NOT:

- Embed executable logic, regular expressions, or templated strings.
- Use prohibited language (see §4).
- Collapse multiple distinct rules into a single record (use one record per fired rule; see §5.2 for the narrow consensus exception).
- Include AI-derived fields. The deterministic engine path is the sole producer of these records. (`reproducibility.deterministic` is `true` by schema constraint.)

## 4. Advisory Language Framework

Per AGENTS.md *Liability Strategy*, every record MUST carry at least one advisory. The schema enforces `advisories` with `minItems: 1`.

### 4.1 MUST-communicate phrasing

Advisories may use language consistent with:

- "likely required permit"
- "commonly encountered requirement"
- "recommended workflow sequencing"
- "additional review recommended"
- "advisory only; not a legal determination"
- "consultant verification recommended"
- "agency coordination recommended"

### 4.2 MUST-NOT-communicate phrasing

Advisories MUST NOT use any of:

- "guaranteed compliance"
- "complete permit certainty"
- "final regulatory determination"
- "legal compliance certification"
- "no further review required"
- "agency approval guaranteed"

Analyst review (T00-09) and a static linter (deferred to T01-07 CI) enforce this list against `advisories[].text`.

### 4.3 Advisory categories

Each advisory carries a `category` so consumers can filter. Categories are an enum, fixed at:

| Category | Use |
|----------|-----|
| `advisory_disclaimer` | The standing AGENTS.md disclaimer that this is not a legal determination. Origin `platform`. Always present. |
| `professional_review_required` | Consultant or engineer must verify before submission. |
| `agency_coordination` | Coordinate with the named agency before action (e.g. USACE pre-application meeting). |
| `freshness_warning` | Source has not been re-verified within the freshness threshold (T02-07). Origin `engine`. |
| `confidence_warning` | Tier 2 or 3 rule fired; consultant attention needed. Origin `engine`. |
| `jurisdictional_overlap` | Project crosses jurisdictions and overlapping rules may apply. |
| `data_gap` | An input the rule examined was missing or partial (e.g. partial GIS overlap). Origin `engine`. |

Categories may be extended only by amending this spec.

### 4.4 Origin

Each advisory's `origin` is one of `rule`, `engine`, or `platform`:

- `rule` — copied verbatim from the rule's `advisories[]`.
- `engine` — injected by the engine in response to a runtime signal (stale freshness, low confidence, partial overlay, missing field).
- `platform` — the standing platform-wide disclaimer required on every record.

The standing platform advisory (canonical text below) MUST appear on every record:

> "Advisory only; not a legal determination. Professional review and agency confirmation are required before submission."

## 5. Record Fields

The complete schema is [`schemas/permit-explanation.schema.json`](./schemas/permit-explanation.schema.json) (JSON Schema draft 2020-12). The schema is the canonical contract; this section describes intent.

### 5.1 Identity & versioning

| Field | Required | Description |
|-------|----------|-------------|
| `schema_version` | yes | Version of *this* explanation schema (currently `1.0.0`). Distinct from `ruleset_version`. Bumped on breaking changes per §12. |
| `record_kind` | yes | `fired` or `not_fired`. Negative explanations (§5.10) use `not_fired`. |
| `evaluation_date` | yes | The ISO date at which the engine evaluated the project. Drives temporal rule selection (T00-03). |
| `ruleset_version` | yes | Object with `content_hash` (sha256 of the effective ruleset snapshot) and optional `commit_sha` / `snapshot_label`. The snapshotting algorithm is owned by T00-03; this spec only consumes the hash. |

### 5.2 `rule_refs[]`

The rule(s) this record explains. Each entry: `rule_id` (matches the kebab-case pattern from T00-01), `rule_version` (semver), and optional `rule_status_at_evaluation` (`effective` or `archived` — `archived` is only valid for grandfathered replays per T00-03).

**Convention: one record per fired rule.** Multiple entries are reserved for the narrow case where two or more rules fire and produce a single consensus permit output (e.g. a state and a county rule that both name the same TPDES permit). Engines SHOULD emit one record per rule by default; consensus merging is an opt-in policy owned by T03-05.

### 5.3 `jurisdiction_chain[]`

Ordered list from Federal down to the most specific applicable jurisdiction for *this project*, per the AGENTS.md hierarchy:

```
federal → state → county → municipality → etj → utility_district → drainage_district → river_authority → special
```

Each entry: `jurisdiction_id` (opaque string; canonical form set by T00-02), `jurisdiction_level` (enum matching T00-01), and optional `canonical_name` (for human readability) and `detection_source` (`user_input`, `gis_auto_detect`, `user_confirmed`, `user_override` — per AGENTS.md *GIS Intake Strategy*).

**Constraint:** The rule's own `jurisdiction_id` MUST appear in the chain. The chain is the *project's* applicable jurisdictions, not the rule's; the rule's jurisdiction must be one of them, otherwise step 1 (jurisdiction) would have failed.

### 5.4 `trigger_path` (required when `record_kind = fired`)

The conditions in the rule's `triggers` tree that were evaluated, mirroring the rule object's logical composition (T00-01 §5.5) plus an `actual_value` and a `matched` boolean at every node.

Structure:

- **Leaf** — `{ field, operator, expected_value, actual_value, matched }`. For `operator = exists`, `expected_value` is omitted.
- **All** — `{ all: [<conditions>], matched }`.
- **Any** — `{ any: [<conditions>], matched }`.
- **Not** — `{ not: <condition>, matched }`.

The root condition lives under `trigger_path.root`. A `matched_summary` plain-language collapsed restatement is included for human review (≤ 500 chars).

For `not_fired` records, `trigger_path` MAY be present up to the failing leaf; for short-circuits earlier than step 4 (trigger conditions), it is omitted (see `negative_explanation` §5.10).

### 5.5 `applicable_thresholds[]`

Numeric thresholds that governed the decision, lifted from matching leaves of `trigger_path`. Each entry:

| Field | Description |
|-------|-------------|
| `field` | Dotted path like `project.acreage`. Must match T00-01 leaf condition pattern. |
| `operator` | One of `>`, `>=`, `<`, `<=`, `=`, `!=`. Non-numeric operators (`contains`, `exists`, etc.) do not appear here. |
| `threshold_value` | The rule's threshold (number or ISO date string). |
| `actual_value` | The observed project value at evaluation time. |
| `units` | Optional human-display units (e.g. `acres`, `days`). Canonical units owned by T02-02 field registry. |

Empty array is valid (rule had no numeric comparisons).

### 5.6 `citations[]`

Copied verbatim from `provenance.source_citations` of every rule in `rule_refs`. Required to be non-empty for fired records (the rule itself requires ≥ 1 citation per T00-01 §5.3.2).

Order is preserved across rule_refs; duplicates collapsed by `reference` string (exact match). Each entry has the same fields as `rule.provenance.source_citations[]` (`citation_type`, `reference`, `url?`, `retrieved_at?`).

### 5.7 `confidence`

The user-facing confidence summary.

```
confidence:
  tier: 1                      # integer 1/2/3, copied from rule
  tier_rationale: string       # plain-language; combines AGENTS.md tier definition with rule context
  freshness:                   # engine-derived per AGENTS.md Data Governance
    last_verified: date
    days_since_verified: int
    stale: bool
    stale_reason: string?      # required when stale = true
```

When multiple rules contribute (multi-entry `rule_refs`), `tier` is the **lowest** (most cautious) across them. The rationale must explain the tie-down: e.g. *"County rule is Tier 2 (locally variable); state rule is Tier 1. Combined permit shown at Tier 2."*

### 5.8 Confidence tier display rules

The schema records the tier as an integer; UI rendering is owned by T07-02. This spec fixes the **plain-language summary** the consultant sees:

| Tier | Summary phrasing (canonical) |
|------|------------------------------|
| 1 | "Statutory and fully verified. Stable requirement." |
| 2 | "Supported and partially verified. May vary by local implementation; consultant confirmation recommended." |
| 3 | "Informational only. Requires consultant confirmation before relying on this permit." |

These canonical strings are the suggested `tier_rationale` opener; rules and engines may append rule-specific context. UI MUST visually distinguish the three tiers (e.g. badge color, icon) but the underlying data is the integer 1/2/3 plus the canonical phrasing.

Freshness is surfaced **independently** of tier, per AGENTS.md *Data Governance*: a Tier 1 statutory rule that hasn't been re-verified in 540 days still raises a `freshness_warning` advisory. The schema models this by carrying both `confidence.tier` and `confidence.freshness.stale`.

### 5.9 `known_unknowns[]`

Union of the rule's `known_unknowns` (origin `rule`) and engine-detected uncertainties (origin `engine`). Engine signals carry an `engine_signal` identifier from this fixed set:

| `engine_signal` | Triggers when |
|------------------|---------------|
| `partial_gis_overlap` | A polygon overlay returned a partial intersection below the engine's overlap threshold. |
| `missing_intake_field` | A field referenced by the rule was not provided in project inputs. |
| `citation_url_unreachable` | A citation's URL failed the last T08-03 reachability check at evaluation time. |
| `jurisdiction_detection_low_confidence` | GIS jurisdiction detection reported a low-confidence overlay. |
| `field_value_coerced` | A field value was type-coerced (e.g. string → number) to evaluate a comparison. |

Engines MAY add new signals only by amending this spec.

### 5.10 `advisories[]`

See §4. At least one entry is always present. Each entry: `text`, `origin` (`rule` / `engine` / `platform`), `category`.

### 5.11 `evaluation_trace[]`

Exactly six entries, one per AGENTS.md / T00-01 §8 evaluation step, in fixed order:

1. `jurisdiction`
2. `temporal_validity`
3. `project_type`
4. `trigger_conditions`
5. `spatial_overlays`
6. `dependencies`

Each entry: `step`, `outcome` (`passed` / `failed` / `skipped`), optional `detail` (one-line explanation).

Semantics:

- `passed` — the engine evaluated this step and the rule survived.
- `failed` — the engine evaluated this step and the rule was eliminated. Only one step can be `failed` in a single record; subsequent steps MUST be `skipped`.
- `skipped` — an earlier step short-circuited; this step was not evaluated.

A `fired` record has all six `passed`. A `not_fired` record has zero or more `passed` followed by exactly one `failed` followed by `skipped` for the remainder.

### 5.12 `negative_explanation` (required when `record_kind = not_fired`)

```
negative_explanation:
  short_circuited_at: enum   # one of the six steps
  reason: string             # human-readable; ≤ 500 chars
```

Negative explanations are **optional emissions**, not optional fields: when the engine emits a `not_fired` record, this object is required. Whether the engine emits negative records by default or only on consultant request is owned by T03-05 / T07-02.

### 5.13 `reproducibility`

The reproducibility contract triplet:

| Field | Description |
|-------|-------------|
| `inputs_hash` | sha256 of the canonical (sorted, normalized) project inputs (intake + confirmed GIS overlays) used at evaluation. |
| `deterministic` | const `true`. Asserts the record was produced by the deterministic path; no AI-derived fields are present. |
| `regeneration_note` | Optional caveat (e.g. "GIS dataset version 2026.04 must be available for replay"). |

`inputs_hash` + `ruleset_version.content_hash` + `evaluation_date` is the **reproducibility key**. See §6.

## 6. Reproducibility Contract

**Guarantee:** Given the same project inputs, the same ruleset version (`content_hash`), and the same `evaluation_date`, the explanation record MUST be byte-identical across runs.

This is the iPermit audit reproducibility guarantee. It is what lets a litigant, an analyst doing a 2030 regression test on a 2026 project, or a benchmark suite (T00-06) verify that the engine's behavior on a frozen ruleset has not drifted.

Implementation requirements imposed on T03-05 (engine):

1. **Canonical JSON serialization.** Records MUST be serialized with:
   - UTF-8 encoding, no BOM.
   - Object keys sorted lexicographically (recursive).
   - No insignificant whitespace (single-line where embedded; multi-line only as pretty-print for human review).
   - Numbers in their shortest JSON-round-trippable form.
2. **Stable ordering inside arrays.** Arrays whose order is semantically significant (`jurisdiction_chain`, `evaluation_trace`) preserve their semantic order. Arrays whose order is incidental (`citations`, `known_unknowns`, `advisories`) are sorted by a deterministic key — citations by `(citation_type, reference)`, known_unknowns by `(origin, text)`, advisories by `(category, origin, text)`.
3. **Canonical input hashing.** `inputs_hash` is computed over the project inputs JSON after the same canonicalization. The input canonicalization spec lives with the intake schema (T06-02); this spec only consumes the hash.
4. **No clock reads.** The engine MUST NOT read wall-clock time during evaluation. `evaluation_date` is a parameter, not `now()`.
5. **No randomness.** Any tie-breaking is deterministic (lexicographic by `rule_id`, then `rule_version`).

If a record fails byte-identical replay against a recorded baseline (T00-06 benchmark suite), that is a P0 incident: either the engine drifted, the ruleset was modified without a snapshot bump, or canonicalization broke.

## 7. Negative Explanations (§5.10 expanded)

A consultant asking *"why didn't the wetlands permit fire on my project?"* receives a `not_fired` record. The record shows:

- The full `evaluation_trace` with exactly one `failed` step.
- A `negative_explanation` naming the short-circuit step and giving a one-line reason.
- `trigger_path` up to the failing leaf, when the failure was at step 4 (`trigger_conditions`). Otherwise `trigger_path` is omitted.
- `applicable_thresholds`, `known_unknowns`, and `citations` MAY be partial or omitted depending on how far evaluation got; the schema does not require them for `not_fired`.

`advisories` is still required (≥ 1). At minimum the standing platform advisory and a `professional_review_required` advisory pointing the consultant to verify the negative result with the agency.

Emission policy (when the engine *produces* a `not_fired` record) is owned by T03-05. Two reasonable policies, both compatible with this spec:

- **On-demand only.** Engine emits `not_fired` records only when a consultant explicitly asks why a permit didn't fire.
- **Eagerly for candidate rules.** Engine emits `not_fired` records for every rule that survived step 1 (jurisdiction) but failed a later step. Step-1 failures are usually too numerous to emit.

## 8. Worked Example

A Texas transmission line project with one stream crossing, asserted federal nexus, located in a USACE-mapped district. The federal CWA Section 404 rule (the T00-01 example rule) fires.

The full record is at [`examples/permit-explanation-example.json`](./examples/permit-explanation-example.json) and [`examples/permit-explanation-example.yaml`](./examples/permit-explanation-example.yaml).

Key observations in the worked example:

- `rule_refs` contains one entry: `us-federal-cwa-section-404-usace-permit@1.0.0`.
- `jurisdiction_chain` is `federal → state → county` — three entries. The rule's `us-federal` jurisdiction is the first.
- `trigger_path.root` is an `all` with two children: a leaf that matched `project.federal_nexus = true`, and an `any` whose first matching child is `project.stream_crossings_count > 0`. The other two `any` branches show `matched: false`.
- `applicable_thresholds` lifts the `project.stream_crossings_count > 0` threshold with `actual_value = 1`.
- `citations` carries all three citations from the rule verbatim.
- `confidence.tier = 1` with the canonical Tier 1 rationale. `freshness.stale = false` (4 days since verified vs a hypothetical 365-day threshold).
- `known_unknowns` has two entries from the rule (origin `rule`) plus one engine-detected `partial_gis_overlap` entry.
- `advisories` has three entries: the standing platform advisory, the two rule advisories, and a `professional_review_required` advisory injected by the engine.
- `evaluation_trace` is all six steps `passed`.
- `reproducibility.deterministic = true`; `inputs_hash` and `ruleset_version.content_hash` are present.

## 9. Validation

Machine-readable schema: [`schemas/permit-explanation.schema.json`](./schemas/permit-explanation.schema.json) — JSON Schema draft 2020-12.

Validate the example locally:

```bash
python3 -c "
import json, jsonschema
schema = json.load(open('docs/specs/schemas/permit-explanation.schema.json'))
example = json.load(open('docs/specs/examples/permit-explanation-example.json'))
jsonschema.Draft202012Validator(schema).validate(example)
print('VALID')
"
```

Wire into CI under T01-07 alongside the rule object schema check.

## 10. Cross-Ticket Boundaries

| Concept | Owner ticket | This spec's treatment |
|---------|--------------|-----------------------|
| Rule object field shapes | T00-01 (merged) | Consumed only; no re-definition. |
| Jurisdiction ID format | T00-02 / T00-08 | Opaque string. |
| Ruleset snapshot algorithm + content_hash computation | T00-03 | Consumed as opaque sha256 string. |
| Dependency / sequencing render | T00-04 | Step 6 outcome only; sequencing UI deferred. |
| Engine implementation | T03-05 | Spec dictates what the engine emits; not how. |
| Permit matrix UI rendering | T07-02 | This spec defines fields; UI maps them. |
| Audit log persistence + retention | T01-04 | Records are persisted there; this spec doesn't define storage. |
| Data freshness scoring threshold | T02-07 | This spec consumes `stale: bool` + reason; threshold owned upstream. |
| Field registry (`project.*`, `geometry.*`) | T02-02 / T06-02 / T05-04 | Patterns mirror T00-01; semantics owned upstream. |
| Benchmark snapshot format | T00-06 | This spec is the input to the benchmark diff; benchmark format is separate. |

## 11. Open Questions Deferred

- **Multi-rule consensus collapsing.** When two rules fire and the engine merges them into one permit output, do we emit one record with two `rule_refs` or two records? Deferred to T03-05 with this spec permitting either.
- **Negative-explanation default policy.** On-demand vs eager emission. Deferred to T03-05.
- **Record signing.** Cryptographic signature of records for tamper-evidence. Deferred to T01-04 (audit log).
- **Localization.** All canonical strings here are English. Localization is deferred indefinitely.

## 12. Change Control

Changes to this spec require:

1. PR review from at least one regulatory analyst (T00-09 SOP) and one engineer.
2. Schema `$id` bump on breaking changes (current: `https://ipermit.dev/schemas/2026-05-24/permit-explanation.schema.json`).
3. `schema_version` const in the schema bumped on breaking changes (current: `1.0.0`).
4. Benchmark regeneration plan: if any required field is added/removed/renamed, all benchmark explanation snapshots (T00-06) must be regenerated under the new schema version.
