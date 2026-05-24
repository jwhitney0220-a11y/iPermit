# Benchmark Project Test Suite Specification

**Ticket:** T00-06
**Status:** Draft — pending peer review per T00-09 SOP
**Owner:** Regulatory architecture
**Source guardrails:** [`/AGENTS.md`](../../AGENTS.md) sections *Benchmark Project Library*, *Rules Engine Architecture*, *Temporal Versioning*, *Human Review Workflow*, *Repository Strategy*
**Related tickets:** T00-01 (Rule Object), T00-03 (Temporal Versioning), T00-04 (Sequencing), T00-05 (Explainability), T01-05 (Monorepo), T02-06 (Dataset Seeding), T04-02 (Regression Framework), T04-03 (Edge Case Framework)

---

## 1. Purpose

Defines the canonical declarative shape of a **benchmark project**: a frozen, reproducible scenario consisting of project inputs and the outputs the deterministic rules engine is expected to produce when evaluating them against a pinned ruleset.

Benchmark projects are the regression substrate for the rules engine. They exist to:

- detect regressions when rules change (T04-02);
- exercise edge cases the analyst team has explicitly committed to (T04-03);
- verify deterministic output stability across releases;
- verify explainability output stability (T00-05);
- support audit replay of historical evaluations;
- gate rule publication (AGENTS.md *Human Review Workflow* — "benchmark tests pass" is a hard precondition).

This spec is normative for any benchmark written to the benchmark library described in §4.

## 2. Status at T00-06: Definitions, Not Executable Tests

Per the roadmap (`docs/roadmap.json`), T00-06 has `downstream: [T02-06, T04-02]`. Until both of those land:

- benchmark records are **design artifacts** — declarative YAML/JSON describing expected behavior;
- they are validated **structurally** against the JSON Schema in §11;
- they are **not** executed against a real ruleset because no real Texas regulatory data exists yet (T02-06);
- they are **not** wired into CI as regression checks because the regression framework does not exist yet (T04-02).

Once T02-06 and T04-02 land:

- the placeholder `ruleset_version.content_hash` values in example benchmarks are replaced with real `sha256:...` hashes derived from the seeded ruleset snapshot;
- T04-02 runs each benchmark and asserts `expected_outputs`, `expected_confidence`, `expected_known_unknowns`, and `expected_explanations` (high-level) match the engine's actual output;
- a regression failure blocks the offending PR.

This sequencing is intentional: benchmarks define the contract before the data exists, so seeding (T02-06) has an explicit target shape to satisfy.

## 3. Non-Goals

This spec **does not** define:

- The rule object shape itself. → **T00-01** ([`rule-object.md`](./rule-object.md))
- The explanation record shape benchmarks compare against. → **T00-05** ([`schemas/permit-explanation.schema.json`](./schemas/permit-explanation.schema.json)). Benchmarks assert *load-bearing* explanation fields (which permit, why it fired); the detailed `evaluation_trace` shape is owned by T00-05 and not duplicated here.
- The temporal selection algorithm that picks which rule version is `effective` on `evaluation_date`. → **T00-03**
- The regression framework — diffing engine output against benchmark expectations, surfacing diffs, gating CI. → **T04-02**
- The edge-case fuzzer that generates synthetic inputs. → **T04-03**
- The actual Texas regulatory data referenced by benchmarks. → **T02-06**

Where another ticket owns a concept, this spec references it by name and uses opaque values (e.g. `rule_id` strings, `content_hash` strings) without defining their semantics.

## 4. File Layout

### 4.1 Long-term home

Per AGENTS.md *Repository Strategy* and T01-05 (Monorepo Initialization), benchmarks live at:

```
/packages/benchmark-projects/
  /simple-linear/
  /multi-county/
  /federal-nexus/
  /conflicting-jurisdiction/
  /temporal-versioning/
  /known-unknown/
  README.md
```

One YAML file per benchmark, named `<benchmark_id>.yaml`. The category directory MUST match the `category` field.

### 4.2 Stub home until T01-05 lands

The monorepo skeleton does not exist yet at T00-06 time. As a stub, the six reference example benchmarks live at:

```
/docs/specs/examples/benchmarks/
  simple-linear-single-county-overhead-distribution.yaml
  multi-county-138kv-transmission-corridor.yaml
  federal-nexus-trinity-river-crossing.yaml
  conflicting-jurisdiction-etj-overlap.yaml
  temporal-versioning-stormwater-2025-change.yaml
  known-unknown-partial-gis-data.yaml
```

When T01-05 creates `/packages/benchmark-projects/`, this directory is migrated wholesale; the `benchmark_id`s remain stable.

### 4.3 File format

YAML is canonical on disk. JSON is acceptable for tooling and CI. Both formats validate against the same schema (§11). YAML is preferred because analysts read these.

One benchmark per file. Files are immutable (§5).

## 5. Immutability Requirement

Per AGENTS.md *Benchmark Project Library*:

> Benchmark projects MUST: remain immutable, be historically reproducible, preserve old outputs, support audit replay.

This spec interprets immutability as follows:

1. **`benchmark_id` is permanent.** Once a benchmark file exists in `main`, its `benchmark_id` is never reused, renamed, or pointed at different content.
2. **Material edits create a new benchmark.** If `expected_outputs`, `expected_confidence`, `expected_known_unknowns`, `expected_explanations`, `project_inputs`, `ruleset_version`, or `evaluation_date` need to change, the original file is preserved untouched and a new benchmark file with a new `benchmark_id` is added. The two coexist.
3. **Cosmetic edits bump `benchmark_version` PATCH.** Typo fixes in `description`, `notes`, or `provenance.reviewer_notes` may be edited in place with a PATCH bump. The schema enforces semver but trusts reviewers on the MAJOR/MINOR/PATCH decision.
4. **The `immutable` field is `true`** on every record. The schema enforces this with `const: true` — any record with `immutable: false` is invalid.
5. **No deletions.** A benchmark deemed obsolete is tagged (`tags: [obsolete]`) but never deleted. Audit replay must always be possible.

T04-02 will enforce immutability mechanically by content-hashing benchmark files and refusing to run if a hash changes without a corresponding new file.

## 6. Versioning

Two independent version axes apply:

### 6.1 Benchmark version (`benchmark_version`)

Semver for the benchmark record itself. Mostly PATCH-only in practice, because material changes go to a new `benchmark_id` (§5).

### 6.2 Ruleset version (`ruleset_version`)

Identifies the snapshot of the rule library the benchmark's `expected_outputs` were computed against. Same shape as T00-05's `ruleset_version` object (`content_hash`, optional `commit_sha`, optional `snapshot_label`) so the regression framework can correlate them directly.

Until T02-06 seeds the rule library, benchmarks use a placeholder `content_hash` of the form `placeholder:<descriptive-slug>`. The schema accepts both `sha256:...` (production) and `placeholder:...` (design-time) so design-time benchmarks remain schema-valid and CI passes from day one.

When T02-06 publishes the first real ruleset snapshot, each example benchmark in §4.2 is upgraded in a single migration PR that swaps placeholders for real hashes. That migration is a PATCH bump (cosmetic from the analyst's perspective) but is the **only** edit ever allowed to a benchmark's `ruleset_version`. After that, ruleset changes produce new benchmarks, not edits.

### 6.3 Historical rule version pins

For `temporal_versioning` benchmarks, `historical_rule_version.rules` pins specific `rule_id@version` strings. This guarantees that if rule `tx-stormwater-permit@1.2.0` is later edited and republished as `1.3.0`, the benchmark still asserts behavior against `1.2.0` and the engine must replay that historical version (T00-03).

## 7. Required Categories

The six categories from AGENTS.md *Benchmark Project Library*. The schema enforces the enum; the library MUST contain at least one benchmark per category before T04-02 goes live.

| Category enum | What it exercises |
|---|---|
| `simple_linear` | Baseline: minimal triggers, single jurisdiction, no spatial overlays beyond county. Output should be small and stable. |
| `multi_county` | Linear project crossing 2+ counties. Verifies jurisdiction iteration, deduplication of identical state-level permits, and per-county delta handling. |
| `federal_nexus` | Project crossing waters of the U.S. or otherwise triggering federal jurisdiction. Verifies federal-tier rules fire and jurisdiction hierarchy ordering. |
| `conflicting_jurisdiction` | ETJ overlap, city-vs-county contradictions, or other cases where lower jurisdictions modify parent requirements. Verifies the conflict resolver (T03-03) preserves parent requirements per AGENTS.md *Rules Engine Architecture*. |
| `temporal_versioning` | Same project evaluated before and after a rule change. Verifies T00-03 selects the correct historical version. Always pinned via `historical_rule_version`. |
| `known_unknown` | Partial input data, ambiguous spatial detection, or other scenarios that should produce uncertainty flags rather than silently default. Verifies T03-06 known-unknown detection. |

Categories are not mutually exclusive in reality — a temporal benchmark may also involve federal nexus — but each benchmark declares ONE primary `category` for organization. Cross-cutting concerns go in `tags`.

## 8. Definition of "Expected Output"

A benchmark passes when the engine's actual evaluation matches the benchmark's expectations on these fields, in order of precedence:

1. **`expected_outputs.permits`** — the set of permit `(name, agency)` tuples MUST match exactly. Order is not significant. Extra permits or missing permits both fail. A `rule_id` pin is checked when present.
2. **`expected_confidence`** — every permit in `expected_outputs.permits` MUST have its tier match. Tier mismatch fails.
3. **`expected_known_unknowns`** — compared as a set. Missing strings fail. Extra strings emitted by the engine produce a warning, not a failure, because T03-06 is allowed to surface additional uncertainties (subset semantics).
4. **`expected_explanations[].trigger_summary`** — high-level keyword-presence check by T04-02 (e.g. the assertion `"federal nexus and stream crossing"` requires both phrases or close synonyms in the rendered explanation). Detailed `evaluation_trace` shape per T00-05 is **not** asserted by benchmarks; T00-05 owns its own contract tests.
5. **`expected_explanations[].expected_rule_id`** (optional) — if set, the rule that fired for this permit must match.
6. **`expected_explanations[].expected_jurisdiction_levels`** (optional) — if set, the jurisdiction chain emitted by the explainer must include each listed level at least once.
7. **`expected_advisories`** (optional) — every listed advisory string must appear verbatim in the rendered output. Used to lock in AGENTS.md *Liability Strategy* language.

Anything not listed above is **out of scope** for benchmark assertions. Sequencing order checks (T00-04 / T03-04), data freshness (T02-07), and AI assistant output (EPIC-09) have their own validation paths.

## 9. How Regression Is Detected

This is the contract T04-02 will implement. Specified here so the regression framework has a target.

For each benchmark:

1. Load the benchmark record. Refuse to run if `immutable != true` or the file's content hash has changed without a new `benchmark_id` (§5).
2. Resolve the ruleset snapshot identified by `ruleset_version`. If the snapshot does not exist, mark the benchmark `unrunnable` and warn, but do not fail CI (this is the pre-T02-06 default state).
3. Construct an evaluation context from `project_inputs` and `evaluation_date`.
4. Run the deterministic engine (T03-02) and the explainer (T03-05) against the snapshot.
5. Compare actual output to expected output using the precedence in §8.
6. Report:
   - **PASS** — all expectations met (extra `known_unknowns` allowed per §8).
   - **FAIL** — any expectation in §8.1–§8.7 violated. CI red.
   - **DRIFT** — the engine emitted permits or known_unknowns that are net-new versus the expectations. Surfaced as a soft warning so analysts can decide whether to add a new benchmark.

Regressions are diffed at the field level so analysts can see *which* expectation diverged, not just that a diff exists.

## 10. Relationship to Other Specs

| Concept | Owner ticket | This spec's behavior |
|---|---|---|
| Rule object fields | T00-01 | References `rule_id` and `rule_id@version` as opaque strings. |
| Explanation record (`evaluation_trace`, `jurisdiction_chain`, etc.) | T00-05 | Benchmarks assert only `trigger_summary`, `expected_rule_id`, `expected_jurisdiction_levels` — load-bearing summaries. The detailed `permit-explanation.schema.json` contract is verified by T00-05's own tests, not benchmarks. |
| Temporal selection | T00-03 | Benchmarks supply `evaluation_date`; T00-03 algorithm picks the effective rule version. Temporal benchmarks pin via `historical_rule_version`. |
| Jurisdiction IDs and aliases | T00-02 / T00-08 | Benchmarks use canonical county/municipality names; the schema does not enforce alias resolution. |
| Confidence tiers | T02-03 | Benchmarks assert tier per permit. Tier semantics defined in AGENTS.md. |
| Regression framework | T04-02 | Implements §9 contract. |
| Real Texas data | T02-06 | Required before any benchmark runs. Until then, ruleset hashes are placeholders (§6.2). |

## 11. Validation

Machine-readable schema: [`schemas/benchmark-project.schema.json`](./schemas/benchmark-project.schema.json) — JSON Schema draft 2020-12.

Reference examples: [`examples/benchmarks/`](./examples/benchmarks/) — one YAML benchmark per required category (§7).

Validate every example locally:

```bash
python3 - <<'PY'
import glob, json, sys
import yaml, jsonschema

schema = json.load(open('docs/specs/schemas/benchmark-project.schema.json'))
validator = jsonschema.Draft202012Validator(schema)
failures = 0
for path in sorted(glob.glob('docs/specs/examples/benchmarks/*.yaml')):
    data = yaml.safe_load(open(path))
    errors = list(validator.iter_errors(data))
    if errors:
        failures += 1
        print(f"INVALID {path}")
        for e in errors:
            print(f"  - {list(e.absolute_path)}: {e.message}")
    else:
        print(f"VALID   {path}")
sys.exit(1 if failures else 0)
PY
```

T01-07 wires this validator into CI so every benchmark file is schema-checked on every PR.

## 12. Authoring Checklist

When an analyst adds a new benchmark:

1. Confirm the scenario is not already covered by an existing benchmark. If a near-duplicate exists, prefer a new `benchmark_id` over editing the existing one (§5).
2. Pick the primary `category`. Add cross-cutting concerns to `tags`.
3. Fill `project_inputs` to mirror the consultant intake form (T06-02) and any GIS auto-detection results (T05-04) under `gis_overlays`.
4. Set `ruleset_version.content_hash` to the current ruleset snapshot. Pre-T02-06, use `placeholder:<slug>`.
5. Set `evaluation_date` deliberately — for temporal benchmarks, pick a date that unambiguously lands on one side of the rule change.
6. Enumerate `expected_outputs.permits`, `expected_confidence`, and `expected_known_unknowns`.
7. Write one `expected_explanations` entry per fired permit. Keep `trigger_summary` plain-language; this is what T04-02 keyword-checks.
8. For temporal benchmarks, populate `historical_rule_version.rules` with `rule_id@version` pins.
9. Fill `provenance.author`, `provenance.created_at`. Add `source_project_reference` only for anonymized real projects.
10. Run the validator (§11). Commit only when VALID.
11. Open a PR. Analyst SOP (T00-09) requires peer review before merge.

## 13. Open Questions Deferred to Other Tickets

- **Snapshot algorithm for `content_hash`** — how the ruleset is hashed and labeled. Owned by T00-03 and the snapshot tooling in T02-06.
- **Diff rendering for failed benchmarks** — UI for surfacing PASS/FAIL/DRIFT to analysts. Owned by T04-05.
- **Fuzzed inputs vs. curated benchmarks** — synthetic edge-case generation lives in T04-03 and is a complement to, not a replacement for, the curated library defined here.
- **Cross-state benchmarks** — once iPermit expands beyond Texas, `project_inputs.state` will exercise non-TX rule branches. Schema already supports any two-letter state code.

## 14. Change Control

Changes to this spec require:

1. PR review from at least one regulatory analyst (T00-09) and one engineer.
2. Schema bump if `benchmark-project.schema.json` changes shape: `$id` URL is versioned by date — bump it on breaking changes.
3. Migration plan for existing benchmarks if any required field is added. Because benchmarks are immutable, "migration" means writing new benchmarks; existing files are not edited.
