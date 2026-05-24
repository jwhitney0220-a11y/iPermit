# Rule Object Specification

**Ticket:** T00-01
**Status:** Draft — pending peer review per T00-09 SOP
**Owner:** Product architecture
**Source guardrails:** [`/AGENTS.md`](../../AGENTS.md) sections *Rule Object Specification*, *Rules Engine Architecture*, *Temporal Versioning*, *Permit Confidence Tiers*
**Related tickets:** T00-02 (Jurisdiction Ontology), T00-03 (Temporal Versioning Model), T00-04 (Dependency & Sequencing), T00-05 (Explainability), T02-02 (Regulatory Intelligence Schema), T02-03 (Confidence Tier Framework), T03-01 (Rules Parser)

---

## 1. Purpose

Defines the canonical declarative shape of a single regulatory rule object. This is the unit of data the deterministic rules engine evaluates against project inputs to produce a permit matrix.

This spec is normative for any rule written to `rules/draft/`, `rules/published/`, `rules/effective/`, or `rules/archived/` (per AGENTS.md *Repository Strategy*).

## 2. Non-Goals

This spec **does not** define:

- The full jurisdiction ontology, hierarchy, or alias system. → **T00-02**
- The temporal evaluation algorithm or how `effective` rules are selected at evaluation time. → **T00-03**
- The dependency graph algorithm or how `sequencing` is rendered into a workflow. → **T00-04**
- The explainability output shape consumers receive. → **T00-05** (this spec defines the *input* fields the explainer consumes, not the output format.)
- The benchmark project format. → **T00-06**
- The runtime evaluation engine itself. → **T03-02**

Where another ticket owns a concept, this spec uses an opaque reference (e.g. `jurisdiction_id` is a string; T00-02 owns what makes that ID valid).

## 3. Design Principles (from AGENTS.md)

A rule object MUST:

1. **Be declarative** — fields describe *what* triggers and *what* outputs; never *how*. No embedded code, no scripting, no expressions beyond the trigger operators in §8.
2. **Be human-readable** — review-able by a regulatory analyst with no engineering background.
3. **Be editable without deployment** — every field is data, not code.
4. **Be version-controlled** — each rule has a `version`, lives in `rules/<status>/`, and changes via PR.
5. **Be testable** — every rule object is valid against the JSON Schema in §10 and can be exercised against a benchmark project (T00-06).
6. **Be explainable** — every rule that can fire MUST carry a plain-language `explanations.trigger_explanation` and citations.

A rule object MUST NOT:

- Contain executable logic, regular expressions, or string templates beyond fixed advisory language.
- Silently delete a parent jurisdiction's requirement. Overrides at lower jurisdictions are explicit via `supersedes` (§7) and the engine's conflict resolver (T03-03).
- Encode legal certainty. All output language is advisory (see AGENTS.md *Liability Strategy*).

## 4. Conceptual Model

A rule answers four questions about one permit:

| Question | Field family |
|----------|--------------|
| **What permit is this?** | identity (§5.1), classification (§5.2) |
| **When does it apply?** | `triggers` (§5.6), `applicable_project_types`, jurisdiction fields |
| **What does the consultant need to do?** | `outputs` (§5.7), `sequencing` (§5.8) |
| **How do we know, and how confident are we?** | `provenance`, `confidence_tier`, `explanations`, `known_unknowns`, `advisories` |

A rule object describes **one permit at one point in its versioning history**. A regulation that changed in 2024 is two separate rule objects (different `version`s, one `superseded_by` the other) — never a single rule with branching logic.

## 5. Field Reference

All fields are JSON-compatible. YAML is the preferred on-disk format for readability; JSON is canonical for tooling.

### 5.1 Identity

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `rule_id` | string | yes | Stable internal ID, lowercase kebab-case, never reused across rules. Convention: `<jurisdiction>-<subject>-<permit-shortname>` e.g. `tx-county-floodplain-development-permit`. |
| `version` | string | yes | Semver of this specific rule version (`MAJOR.MINOR.PATCH`). Bump MAJOR when the trigger logic or output materially changes; MINOR when adding non-breaking detail; PATCH for typos or citation refreshes. |
| `title` | string | yes | Short human-readable title shown in analyst tools. ≤ 80 chars. |
| `permit_name` | string | yes | Canonical permit name as the issuing agency uses it. |
| `permit_code` | string | no | Official permit code or short form if any (e.g. `CWA Section 404`, `TPDES MSGP`). |

### 5.2 Classification

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `jurisdiction_level` | enum | yes | One of: `federal`, `state`, `county`, `municipality`, `etj`, `utility_district`, `drainage_district`, `river_authority`, `special`. Matches AGENTS.md jurisdiction hierarchy. |
| `jurisdiction_id` | string | yes | Canonical jurisdiction ID. Format and registry defined by T00-02. This spec treats it as an opaque string. |
| `source_agency` | string | yes | Canonical name of the agency that issues, enforces, or authoritatively interprets the permit. |
| `applicable_project_types` | array&lt;string&gt; | yes | Project type tokens this rule applies to. Min 1. Examples: `transmission_line`, `distribution_line`, `substation`, `linear_general`, `nonlinear_general`. Token registry is owned by T02-02. |

### 5.3 Confidence & Provenance

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `confidence_tier` | integer (1\|2\|3) | yes | Per AGENTS.md *Permit Confidence Tiers*. Tier 1 = fully verified and statutory; Tier 2 = partially verified, locally variable; Tier 3 = informational. |
| `provenance` | object | yes | See §5.3.1. |

#### 5.3.1 `provenance` sub-object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_citations` | array&lt;object&gt; | yes (min 1) | One or more authoritative sources. See §5.3.2. |
| `last_verified` | date (YYYY-MM-DD) | yes | Date an analyst last confirmed every citation and the trigger/output content. Feeds data freshness scoring (T02-07). |
| `reviewer` | string | no | Analyst identifier or initials. Optional in draft; required for `published`/`effective` (enforced by T08-04 publication workflow, not this schema). |
| `reviewer_notes` | string | no | Free-text notes from the last review. |

#### 5.3.2 `source_citations[]` entries

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `citation_type` | enum | yes | One of: `statute`, `regulation`, `ordinance`, `agency_guidance`, `form`, `website`. |
| `reference` | string | yes | Citation text (e.g. `33 U.S.C. § 1344`, `Travis County Code §82.301`). |
| `url` | string (uri) | no | Source URL if one exists. Monitored for reachability by T08-03. |
| `retrieved_at` | date (YYYY-MM-DD) | no | When the URL was last successfully fetched. |

### 5.4 Versioning & Lifecycle

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | enum | yes | One of: `draft`, `published`, `effective`, `archived`. Mirrors directory placement under `rules/<status>/`. Definitions in AGENTS.md *Temporal Versioning*. |
| `effective_from` | date | conditional | Required when `status` is `effective` or `archived`. Date the rule begins governing evaluations. |
| `effective_to` | date | no | Date the rule stops governing evaluations. Required when `status` is `archived` unless `superseded_by` is set. |
| `supersedes` | array&lt;string&gt; | no | List of `rule_id@version` strings that this version replaces. |
| `superseded_by` | string | no | `rule_id@version` of the rule that replaces this one. Set when this rule transitions to `archived` because of a newer version. |

T00-03 defines how the engine selects which rule version is `effective` for a given evaluation date.

### 5.5 Logical Composition: `triggers`

`triggers` is **required**. It is either a single leaf condition or a logical composition.

**Leaf condition:**

```yaml
triggers:
  field: project.acreage
  operator: ">="
  value: 10
```

**Composition operators:** `all`, `any`, `not`.

```yaml
triggers:
  all:
    - field: project.linear
      operator: "="
      value: true
    - any:
        - field: project.stream_crossings_count
          operator: ">"
          value: 0
        - field: geometry.intersects_usace_district
          operator: exists
```

Compositions are recursive. There is no depth limit in the schema; analyst SOP (T00-09) will recommend ≤ 3 levels for readability.

Field paths are dotted, snake_case identifiers rooted at a known namespace:

- `project.*` — values from the consultant intake form (T06-02).
- `geometry.*` — values from GIS auto-detection (T05-03/T05-04).
- `derived.*` — values computed by the engine from other inputs.

The field registry (what `project.*` paths exist) is owned by T02-02 and T06-02. This spec only defines the *shape* of a field reference.

### 5.6 `outputs`

What the consultant sees when the rule fires.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `permits` | array&lt;object&gt; | yes (min 1) | The permit(s) triggered. Each entry: `name` (string, required), `code` (string, optional), `agency` (string, required). |
| `forms` | array&lt;object&gt; | no | Each entry: `name` (required), `form_number` (optional), `url` (optional, uri). |
| `submission` | object | no | Submission mechanism. Fields: `submission_url` (uri), `submission_email` (string), `submission_method` (string, e.g. `online_portal`, `mail`, `in_person`). |
| `agencies` | array&lt;string&gt; | no | Additional agencies involved beyond `source_agency` (e.g. consulting agencies, coordinating bodies). |

### 5.7 `sequencing` (optional)

Used by T03-04 to render workflow order. The full sequencing model is owned by T00-04; this spec only defines the storage fields.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prerequisites` | array&lt;string&gt; | no | `rule_id`s that should be satisfied before pursuing this permit. |
| `parallel_with` | array&lt;string&gt; | no | `rule_id`s that can be pursued in parallel. |
| `typical_lead_time_days` | integer | no | Typical agency processing time in calendar days. Advisory only. |
| `notes` | string | no | Free-text sequencing notes (e.g. *"Submit after USACE PCN response."*). |

### 5.8 Explainability

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `explanations` | object | yes | See §5.8.1. |
| `known_unknowns` | array&lt;string&gt; | no | Stated uncertainties consultants should verify. Surfaced in the permit matrix. |
| `advisories` | array&lt;string&gt; | no | Mandatory advisory text to display alongside this permit. Must use AGENTS.md-compliant language (no "guaranteed compliance" etc.). |

#### 5.8.1 `explanations` sub-object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trigger_explanation` | string | yes | Plain-language sentence stating *why* this rule applies. ≤ 280 chars. Shown to consultants. |
| `threshold_summary` | string | no | One-line summary of governing thresholds when relevant. |
| `jurisdiction_summary` | string | no | One-line summary of why the jurisdiction applies. |

### 5.9 Optional metadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tags` | array&lt;string&gt; | no | Analyst-facing tags for filtering. |
| `notes` | string | no | Free-text internal notes. Not shown to consultants. |

## 6. Required-Field Summary

A minimal valid rule object has: `rule_id`, `version`, `title`, `permit_name`, `jurisdiction_level`, `jurisdiction_id`, `source_agency`, `applicable_project_types`, `confidence_tier`, `provenance` (with `source_citations` and `last_verified`), `status`, `triggers`, `outputs` (with at least one `permits` entry), `explanations` (with `trigger_explanation`).

Everything else is optional or conditional.

## 7. Trigger Operator Reference

Operators come from AGENTS.md §*Rule Object Specification*. Symbols are used as JSON values verbatim.

| Operator | Applies to field types | `value` required? | Semantics |
|----------|------------------------|-------------------|-----------|
| `=` | scalar (string, number, boolean) | yes | Field value equals `value`. |
| `!=` | scalar | yes | Field value does not equal `value`. |
| `>` | number, date | yes | Field value is strictly greater than `value`. |
| `>=` | number, date | yes | Field value is greater than or equal to `value`. |
| `<` | number, date | yes | Field value is strictly less than `value`. |
| `<=` | number, date | yes | Field value is less than or equal to `value`. |
| `contains` | string, array | yes | Field (string) contains the substring `value`, or field (array) contains the element `value`. |
| `intersects` | array of jurisdiction or geometry IDs | yes | Field (array) shares at least one element with `value` (array). Used for spatial overlay checks against detected jurisdictions. |
| `exists` | any | no | Field is present and non-null. Use for optional inputs like `geometry.fema_floodplain_overlap_acres`. |
| `in` | scalar | yes (array) | Field value is one of the elements in `value` (array). |
| `not_in` | scalar | yes (array) | Field value is none of the elements in `value` (array). |

Type validation between operator and field value is the runtime engine's job (T03-01), informed by the field registry. The schema in §10 does not enforce per-operator value types.

## 8. Rule Evaluation Order

From AGENTS.md *Rule Object Specification*. The engine (T03-02) evaluates in this order:

1. **Jurisdiction** — does this rule's `jurisdiction_id` apply to the project's detected jurisdictions?
2. **Temporal validity** — is this rule `effective` for the project's evaluation date? (T00-03)
3. **Project type** — does the project's type appear in `applicable_project_types`?
4. **Trigger conditions** — evaluate `triggers` against project inputs.
5. **Spatial overlays** — evaluate any `geometry.*` field references in triggers against GIS results.
6. **Dependencies** — resolve `sequencing.prerequisites` and conflicts. (T03-03 / T03-04)

A rule that fails any earlier step is short-circuited; later steps are not evaluated. The explainer (T00-05) reports which step short-circuited a rule.

## 9. Lifecycle Transitions

```
draft  ──analyst review (T00-09)──▶  published
published  ──effective_from reached──▶  effective
effective  ──superseded or effective_to reached──▶  archived
draft  ──discarded──▶  (deleted, not archived)
```

A rule MUST live in the directory matching its `status` (per AGENTS.md *Repository Strategy*). The publication workflow (T08-04) moves files between directories atomically.

`published` is distinct from `effective`: a rule may be approved and pre-staged for a future regulatory change without yet governing evaluations.

## 10. Validation

Machine-readable schema: [`schemas/rule-object.schema.json`](./schemas/rule-object.schema.json) — JSON Schema draft 2020-12.

Reference example: [`examples/rule-object-example.yaml`](./examples/rule-object-example.yaml) and [`examples/rule-object-example.json`](./examples/rule-object-example.json) (same content in both formats).

Validate the example locally:

```bash
python3 -c "
import json, jsonschema
schema = json.load(open('docs/specs/schemas/rule-object.schema.json'))
example = json.load(open('docs/specs/examples/rule-object-example.json'))
jsonschema.Draft202012Validator(schema).validate(example)
print('valid')
"
```

This validation should be wired into CI under T01-07.

## 11. Open Questions Deferred to Other Tickets

- **Jurisdiction ID format** — opaque string here; canonical form set by T00-02 / T00-08.
- **Project field registry** — what `project.*` and `geometry.*` paths are valid; set by T02-02 + T06-02 + T05-04.
- **Conflict resolution between rules** — when two rules from different jurisdiction levels produce conflicting outputs, the resolver chooses; algorithm in T03-03.
- **Data freshness scoring** — `last_verified` feeds the freshness model in T02-07; this spec doesn't compute it.
- **Output rendering** — how `explanations`, `known_unknowns`, and `advisories` are laid out in the consultant-facing permit matrix; set by T07-02.
- **Rule diffing** — comparison between two versions of the same `rule_id`; algorithm in T04-04.

## 12. Change Control

Changes to this spec require:

1. PR review from at least one regulatory analyst (T00-09 SOP) and one engineer.
2. Schema bump if the JSON Schema changes shape: `schemas/rule-object.schema.json` carries a `$id` URL versioned by date — bump it on breaking changes.
3. Migration plan for existing rules if any required field is added or removed.
