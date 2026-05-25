# Ingestion Template Reference

**Ticket:** T02-06 — Dataset Ingestion Framework
**Related specs:** `docs/specs/rule-object.md` (T00-01), `docs/specs/jurisdiction-naming.md` (T00-08), `docs/specs/analyst-sop.md` (T00-09)

---

> **IMPORTANT — Non-Authoritative Samples Only.**
> The sample rows in `rule-template.csv` and `rule-template.json` exist solely
> to exercise the ingestion pipeline in tests. They do **not** represent real
> Texas regulatory requirements. Real rules must be authored by a licensed
> regulatory analyst per `docs/specs/analyst-sop.md` (T00-09) with primary-source
> citations. Do **not** use these samples for any permit determination.

---

## Files in This Directory

| File | Purpose |
|------|---------|
| `rule-template.csv` | CSV template with a single SAMPLE row. Use as a starting point for bulk ingestion from a spreadsheet. |
| `rule-template.json` | JSON template with one SAMPLE rule object. Use for structured single-rule authoring or small batches. |
| `README.md` | This file. |

---

## Column Reference (CSV)

The CSV header row lists every column in the order expected by the pipeline.
Required columns must be non-empty for every real data row. Optional columns
may be left blank; the pipeline treats blank cells as absent.

### Identity

| Column | Required | Description |
|--------|----------|-------------|
| `rule_id` | yes | Stable kebab-case ID — e.g. `tx-travis-floodplain-dev-permit`. Pattern: `^[a-z][a-z0-9]*(-[a-z0-9]+)+$`. Never reused. See T00-09 §3.4 for naming conventions. |
| `version` | yes | Semver string — e.g. `1.0.0`. Bump MAJOR for material logic changes. |
| `title` | yes | Short human-readable title, ≤ 80 characters. |
| `permit_name` | yes | Canonical permit name as the issuing agency uses it. |
| `permit_code` | no | Official permit code if any — e.g. `CWA Section 404`. |

### Classification

| Column | Required | Description |
|--------|----------|-------------|
| `jurisdiction_level` | yes | One of: `federal`, `state`, `county`, `municipality`, `etj`, `utility_district`, `drainage_district`, `river_authority`, `special`. Accepts snake_case or kebab-case — e.g. both `river_authority` and `river-authority` are normalised by the pipeline. |
| `jurisdiction_id` | yes | Canonical jurisdiction ID per T00-08 §3 — e.g. `us-tx`, `us-tx-county-travis`. Must match a registered jurisdiction. |
| `source_agency` | yes | Full canonical name of the issuing/enforcing agency. No abbreviations (per T00-08 §4.2). |
| `applicable_project_types` | yes | Pipe-separated token list — e.g. `transmission_line\|linear_general`. Min 1 token. Token registry owned by T02-02. |

### Confidence & Provenance

| Column | Required | Description |
|--------|----------|-------------|
| `confidence_tier` | yes | Integer `1`, `2`, or `3` per AGENTS.md *Permit Confidence Tiers*. |
| `last_verified` | yes | Date the analyst last confirmed citations, in `YYYY-MM-DD` format. |
| `reviewer` | no | Analyst identifier or initials. Required for `published`/`effective` rules. |
| `reviewer_notes` | no | Free-text notes from the reviewing analyst. |
| `source_citations` | yes | JSON array of citation objects. Each object: `{"citation_type": "...", "reference": "...", "url": "...", "retrieved_at": "YYYY-MM-DD"}`. `citation_type` is one of: `statute`, `regulation`, `ordinance`, `agency_guidance`, `form`, `website`. See T00-01 §5.3.2. |

### Lifecycle

| Column | Required | Description |
|--------|----------|-------------|
| `status` | yes | One of: `draft`, `published`, `effective`, `archived`. |
| `effective_from` | conditional | `YYYY-MM-DD`. Required when `status` is `effective` or `archived`. |
| `effective_to` | no | `YYYY-MM-DD`. Required for `archived` unless `superseded_by` is set. |
| `supersedes` | no | JSON array of `rule_id@version` strings this rule replaces — e.g. `["tx-travis-dev-permit@1.0.0"]`. |
| `superseded_by` | no | `rule_id@version` string of the rule that replaces this one. |

### Logic & Outputs

| Column | Required | Description |
|--------|----------|-------------|
| `triggers` | yes | JSON object — a leaf condition or composition (`all`/`any`/`not`). See T00-01 §5.5 for the full trigger shape. |
| `outputs` | yes | JSON object with at least `"permits": [{"name": "...", "agency": "..."}]`. See T00-01 §5.6. |
| `explanations` | yes | JSON object with required `"trigger_explanation"` (≤ 280 chars, plain language). See T00-01 §5.8. |
| `sequencing` | no | JSON object with optional `prerequisites`, `parallel_with`, `typical_lead_time_days`, `notes`. |

### Advisory & Metadata

| Column | Required | Description |
|--------|----------|-------------|
| `known_unknowns` | no | JSON array of strings describing stated uncertainties. |
| `advisories` | no | JSON array of mandatory advisory strings. Must use compliant language per AGENTS.md *Liability Strategy*. |
| `tags` | no | JSON array of analyst-facing tag strings. |
| `notes` | no | Free-text internal notes (not consultant-visible). |

---

## Canonical Naming and Alias Rules

The ingestion pipeline does **not** resolve aliases to canonical IDs — that is the analyst's job before creating the CSV/JSON. Follow these rules:

### `jurisdiction_id`

Use the canonical jurisdiction ID from the registry (T00-08). The ID is a kebab-case slug following the grammar `<country>-<state>-<level>-<name-segments>`:

```
us                          # United States (federal root)
us-tx                       # State of Texas
us-tx-county-travis         # Travis County
us-tx-municipality-austin   # City of Austin
us-tx-etj-austin            # City of Austin ETJ
us-tx-river-authority-lcra  # Lower Colorado River Authority
```

Do **not** invent IDs — every `jurisdiction_id` must exist in the jurisdiction registry. If the jurisdiction does not yet exist, open a T00-08 record first.

### `jurisdiction_level`

The pipeline normalises both formats:
- snake_case (schema form): `river_authority`, `utility_district`, `drainage_district`
- kebab-case (ID-segment form): `river-authority`, `utility-district`, `drainage-district`

Both are accepted in the CSV/JSON; they are normalised to snake_case before validation.

### `source_agency`

Use the full official name without abbreviation (per T00-08 §4.2). Abbreviations and aliases must be in the jurisdiction record's `aliases` array, not in the rule object. Examples:
- Use: `Lower Colorado River Authority`, not `LCRA`
- Use: `Texas Commission on Environmental Quality`, not `TCEQ`

### `applicable_project_types` in CSV

Pipe-separate multiple tokens: `transmission_line|linear_general|substation`

In JSON, use a standard array: `["transmission_line", "linear_general"]`

---

## Using the Pipeline

```python
from ipermit_regulatory.ingest import load_rules_from_json, load_rules_from_csv

# Dry-run: validate only, no DB writes
results = load_rules_from_json("templates/ingestion/rule-template.json", dry_run=True)

# Live load
from sqlalchemy.orm import Session
with Session(engine) as session:
    results = load_rules_from_csv("my-rules.csv", session)
    session.commit()
```

The pipeline raises `IngestError` on the first failing row, including the row index and offending field path. See `packages/regulatory-models/ipermit_regulatory/ingest.py` for the full API.

---

## Comment Rows in CSV

Any row whose first cell begins with `#` is treated as a documentation comment and skipped by the pipeline. The sample in `rule-template.csv` uses this to embed instructions without breaking automated parsing.

---

## See Also

- `docs/operations/ingestion-playbook.md` — step-by-step workflow for seeding real rules (T02-06)
- `docs/specs/rule-object.md` — full rule object specification (T00-01)
- `docs/specs/jurisdiction-naming.md` — canonical naming standard (T00-08)
- `docs/specs/analyst-sop.md` — analyst workflow SOP (T00-09)
