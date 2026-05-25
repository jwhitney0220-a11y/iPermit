# Dataset Seeding & Ingestion Playbook

**Ticket:** T02-06 — Initial Dataset Seeding & Ingestion Framework
**Status:** Draft
**Audience:** Regulatory analysts (data authors), engineering leads supervising the seeding effort
**Related tickets:** T00-01 (Rule Object), T00-08 (Jurisdiction Naming), T00-09 (Analyst SOP), T02-01 (Jurisdiction DB), T02-07 (Freshness), T08-04 (Publication Tooling)
**Related files:** `templates/ingestion/rule-template.csv`, `templates/ingestion/rule-template.json`, `templates/ingestion/README.md`

---

> **Scheduling note (from AGENTS.md):**
> The actual work of translating real Texas utility/transmission regulatory knowledge
> into structured, normalised, citation-backed rule objects — for the first time, with
> no existing template — is the **single highest-variance task in the roadmap**.
> Build scheduling buffer here. Seeding velocity will set the pace for rules engine
> validation, benchmark testing, and downstream QA.

> **Non-Authoritative Samples:**
> All files under `templates/ingestion/` contain SAMPLE rows that exist solely to
> exercise the ingestion pipeline. They do **not** represent real Texas regulatory
> requirements and must not be used for permit determination. Real data must come from
> analyst-authored primary sources per T00-09.

---

## 1. Overview

This playbook covers the end-to-end workflow for converting Texas utility/transmission regulatory information into live, validated rule objects in the iPermit platform. It maps to ticket T02-06 and complements the Analyst SOP (T00-09 / `docs/specs/analyst-sop.md`), which remains the authoritative source for per-rule authoring standards.

The pipeline supports two input formats:
- **CSV** (`templates/ingestion/rule-template.csv`) — bulk input from a spreadsheet
- **JSON** (`templates/ingestion/rule-template.json`) — structured single-rule authoring

Both formats go through the same normalisation → validation → persistence pipeline in `packages/regulatory-models/ipermit_regulatory/ingest.py`.

---

## 2. Prerequisites

Before beginning a seeding run:

1. **Jurisdiction registry must be populated.** Every `jurisdiction_id` in your rule set must exist in the jurisdiction table. If jurisdictions are missing, seed them first via the T02-01 jurisdiction ingestion process (see `docs/operations/environments.md`).
2. **Source material in hand.** Analysts must have primary-source documents (statutes, regulations, ordinances, agency guidance) physically accessible. The pipeline cannot validate source accuracy; it validates structure only.
3. **Python environment.** `ipermit_regulatory` package must be importable (`tests/conftest.py` handles this automatically for tests; for scripts, ensure the virtual environment is active).
4. **Database connection.** Live loads require a `Session` connected to the target environment. Dry-run validation can run without a DB connection.

---

## 3. Step-by-Step Workflow

### Step 1: Source Identification and Collection

Follow T00-09 §2 for source collection. For each permit type you intend to seed:

- Identify the governing statute, regulation, or ordinance.
- Record the full citation and URL.
- Archive a Wayback Machine snapshot (`https://web.archive.org/save/<url>`).
- Note the retrieval date.
- Capture the exact text passage that establishes the trigger threshold.

Do **not** proceed to rule drafting until you have at least one primary source per T00-09 §2.1.

### Step 2: Spreadsheet Normalisation

Many initial datasets come from existing spreadsheets, agency inventories, or analyst notes. Before using the template, normalise the raw data:

1. **One row = one permit.** Split combined entries per T00-09 §3.1.
2. **Assign a `rule_id`.** Follow the naming convention in T00-09 §3.4:
   `<jurisdiction-token>-<subject>-<permit-shortname>`. Pattern: `^[a-z][a-z0-9]*(-[a-z0-9]+)+$`.
3. **Assign an initial `version`.** Start at `1.0.0` for all first-generation rules.
4. **Verify `jurisdiction_id`.** Look up the canonical ID in the jurisdiction registry. Do not invent IDs (see T00-08 §3.6).
5. **Expand `source_agency` to full official name.** No abbreviations per T00-08 §4.2.
6. **Categorise `applicable_project_types`.** Use tokens from the registry owned by T02-02.

### Step 3: Canonical Naming Enforcement

Before filling the template, enforce canonical naming across every free-text field:

**`jurisdiction_id`**: Must match an existing registry record. Use the kebab-case slug per T00-08 §3.2. Examples:
- Travis County: `us-tx-county-travis`
- City of Austin: `us-tx-municipality-austin`
- LCRA: `us-tx-river-authority-lcra`

**`source_agency`**: Full official name, no abbreviations. Example:
- Use `Texas Commission on Environmental Quality`, not `TCEQ`
- Use `Lower Colorado River Authority`, not `LCRA`

**`jurisdiction_level`**: Use schema enum values (snake_case). The pipeline also accepts kebab-case from spreadsheets and normalises automatically. Valid values: `federal`, `state`, `county`, `municipality`, `etj`, `utility_district`, `drainage_district`, `river_authority`, `special`.

### Step 4: Alias Mapping

During seeding, you may encounter source documents that use informal names, abbreviations, or aliases for jurisdictions and agencies. Resolution process:

1. Check the jurisdiction registry `aliases` array for the matching canonical entry.
2. If found, use the `jurisdiction_id` from the matched record.
3. If not found, add the alias to the jurisdiction record first (T02-01 workflow) before seeding the rule.
4. Record the alias source in the jurisdiction record's `source` field for future disambiguation (T02-06 alias matching).

Never embed non-canonical names in `jurisdiction_id` or `source_agency` in the rule object.

### Step 5: Source Verification

For each citation you plan to include:

- [ ] URL opens and returns the cited content.
- [ ] Citation text matches the formal legal style for the source type (T00-09 §2.2).
- [ ] Wayback Machine snapshot exists.
- [ ] `retrieved_at` date is today.
- [ ] For Tier 1 rules: at least one citation is a statute, regulation, or ordinance.
- [ ] For Tier 3 rules: `known_unknowns` entries describe what is not yet verified.

### Step 6: Template Population

Copy the appropriate template and fill it with real data:

```bash
# CSV path for a new batch
cp templates/ingestion/rule-template.csv my-rules-batch-YYYY-MM-DD.csv

# JSON path for a single rule
cp templates/ingestion/rule-template.json rules/draft/my-rule-id.json
```

Column reference: see `templates/ingestion/README.md`.

Key encoding rules for CSV:
- `applicable_project_types`: pipe-separated — `transmission_line|linear_general`
- `source_citations`, `triggers`, `outputs`, `explanations`: valid JSON strings in the cell
- Comment rows (first cell starts with `#`) are skipped by the pipeline
- Leave optional columns blank — do not write `null` or `none`

### Step 7: Dry-Run Validation

Always validate before a live load. The dry-run validates every row against the canonical JSON Schema without writing to the database.

```python
from ipermit_regulatory.ingest import load_rules_from_csv, load_rules_from_json

# CSV dry-run
results = load_rules_from_csv("my-rules-batch.csv", dry_run=True)
print(f"Validated {len(results)} rules — no DB writes.")

# JSON dry-run
results = load_rules_from_json("rules/draft/my-rule.json", dry_run=True)
```

Any `IngestError` will include the row index and the offending field path. Fix every error before proceeding.

Alternatively, from the command line:

```bash
python -c "
from ipermit_regulatory.ingest import load_rules_from_csv
r = load_rules_from_csv('my-rules-batch.csv', dry_run=True)
print(f'OK: {len(r)} rules valid')
"
```

### Step 8: Live Load

After dry-run passes, load into the target database. Always load into staging first; never load directly to production without a staging run.

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from ipermit_persistence import Base
from ipermit_regulatory.ingest import load_rules_from_csv

engine = create_engine("postgresql+psycopg2://...")
with Session(engine) as session:
    results = load_rules_from_csv("my-rules-batch.csv", session)
    session.commit()
    print(f"Loaded {len(results)} rules.")
```

If a load fails mid-batch, the session is not committed and the database remains clean. Fix the error row, re-run.

### Step 9: Post-Load Verification

After a successful load:

1. Query the `regulatory_rule` table to confirm expected row counts.
2. Query `regulatory_citation` to confirm citation rows were created.
3. Run schema validation against the loaded documents:
   ```bash
   python scripts/checks/validate_schemas.py
   ```
4. Run the full test suite: `python -m pytest tests/ -q`

### Step 10: PR and Peer Review

Seeded rules follow the standard PR and peer review workflow per T00-09 §7:

1. Stage the rule files and any new CSV/JSON source files:
   ```bash
   git add rules/draft/<rule-id>.yaml
   ```
2. Commit with the standard message format: `<rule-id> v<version>: <one-line summary>`
3. Open a PR targeting `main`.
4. Request peer review from a non-drafting analyst.
5. The reviewing analyst runs `load_rules_from_json(..., dry_run=True)` locally to confirm schema validity.
6. Publication follows T00-09 §8 after peer review sign-off.

---

## 4. Provenance Preservation

Every rule that enters the platform must preserve its provenance trail:

| Provenance element | Field in rule object | Ingestion requirement |
|-------------------|---------------------|-----------------------|
| Statute or regulation text | `provenance.source_citations[].reference` | Full formal citation |
| Source URL | `provenance.source_citations[].url` | Exact URL; do not shorten |
| Retrieval date | `provenance.source_citations[].retrieved_at` | Date you accessed the URL (YYYY-MM-DD) |
| Last analyst verification | `provenance.last_verified` | Today's date at time of drafting |
| Reviewing analyst | `provenance.reviewer` | Initials or analyst ID; required for published/effective |
| Archive snapshot | `provenance.reviewer_notes` | Wayback URL; required per T00-09 §2.2 |

Provenance is the primary audit artifact. A rule with missing or incomplete provenance will not pass the publication checklist (T00-09 §8.2).

---

## 5. Validation Gate Summary

The pipeline enforces three gates in sequence:

1. **Normalisation** — coerce types, expand aliases, map kebab→snake jurisdiction levels. Failure: `IngestError` with field name.
2. **JSON Schema validation** — validate against `docs/specs/schemas/rule-object.schema.json` (Draft 2020-12). Failure: `IngestError` with field path and constraint message.
3. **DB persistence** — `add_rule` writes to `regulatory_rule` and `regulatory_citation`. Failure: SQLAlchemy error (typically a constraint violation).

Gate 1 and Gate 2 run in both dry-run and live modes. Gate 3 is skipped in dry-run mode.

---

## 6. Error Handling Reference

| Error type | Likely cause | Resolution |
|-----------|-------------|------------|
| `IngestError: row N: field 'rule_id': missing` | Required cell blank in CSV | Fill the cell |
| `IngestError: row N: field 'jurisdiction_level': unknown` | Typo or unsupported value | Use one of the valid enum values |
| `IngestError: row N: field '<root>': 'triggers' is a required property` | `triggers` column blank | Provide a valid JSON trigger object |
| `IngestError: row N: field 'triggers': JSON parse failed` | Malformed JSON in CSV cell | Fix JSON syntax in cell (check quotes and brackets) |
| `IngestError: row N: field 'provenance': 'source_citations' is required` | `source_citations` column blank | Add at least one citation |
| `jsonschema.ValidationError` (outside pipeline) | Calling `validate_rule` directly | Use `IngestError` catch in pipeline |
| SQLAlchemy `IntegrityError` on `rule_id`+`version` | Duplicate rule loaded | Check for duplicate rows; bump version or skip |

---

## 7. Seeding Scope and Prioritisation

For the Texas MVP (AGENTS.md *Geographic Scope*), seed rules in this order:

1. **Federal overlays** — USACE Section 404/401, EPA NPDES/TPDES general permits. These apply broadly and are the highest-confidence (Tier 1) rules.
2. **State permits** — TCEQ stormwater, TPDES MSGP, TxDOT right-of-way, TPWD wildlife habitat. Apply statewide.
3. **River authority overlays** — LCRA, BRA, SARA, TRA. Apply across their respective watersheds.
4. **County-level** — county floodplain development permits for the highest-activity counties first (Travis, Harris, Bexar, Dallas, Tarrant).
5. **Municipality-level** — Austin, Houston, San Antonio, Dallas, Fort Worth. Focus on ROW excavation and construction permits.
6. **Special jurisdictions** — Edwards Aquifer Authority and others where project overlap is likely.

Do not seed ETJ or utility-district rules until their parent jurisdiction rules are in place.

---

## 8. Texas-Specific Guidance

Per `docs/specs/jurisdiction-naming.md` §12:

- **All 254 Texas counties** must be present in the jurisdiction registry before county-level rules are loaded. Verify registry completeness before seeding county rules.
- **ETJ rules**: S.B. 2038 (88th Legislature, 2023) affects ETJ boundaries. Model ETJ releases as geometry changes, not new jurisdiction records.
- **River authorities** (LCRA, BRA, SARA, TRA) are state-chartered; their `jurisdiction_level` is `river_authority` and their `jurisdiction_id` parent is `us-tx`, not any county.
- **Utility districts**: spell out type in `source_agency` (`Municipal Utility District`, not `MUD`). Parent is `us-tx`.

---

## 9. Change Control

Changes to seeded rules follow the standard versioning and publication workflow (T00-09 §3.5, §8–§9):

- PATCH bump: citation refresh, URL update, `last_verified` update.
- MINOR bump: non-breaking additions (new `known_unknowns`, expanded advisories).
- MAJOR bump: material trigger or output change — creates a new rule object, archives the prior version.

Never edit a file under `rules/effective/` or `rules/archived/` directly. Always version.

---

## 10. Reference

| Resource | Location |
|----------|----------|
| Rule object specification (T00-01) | `docs/specs/rule-object.md` |
| Canonical naming standard (T00-08) | `docs/specs/jurisdiction-naming.md` |
| Analyst SOP (T00-09) | `docs/specs/analyst-sop.md` |
| Rule object JSON Schema | `docs/specs/schemas/rule-object.schema.json` |
| CSV template | `templates/ingestion/rule-template.csv` |
| JSON template | `templates/ingestion/rule-template.json` |
| Template column reference | `templates/ingestion/README.md` |
| Ingest pipeline source | `packages/regulatory-models/ipermit_regulatory/ingest.py` |
| Ingestion tests | `tests/regulatory/test_ingest.py` |
