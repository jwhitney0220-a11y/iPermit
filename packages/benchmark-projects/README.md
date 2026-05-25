# packages/benchmark-projects

The executable benchmark regression corpus and runner for the deterministic
rules engine. Benchmark format is defined by [T00-06](../../docs/specs/benchmarks.md)
([`benchmark-project.schema.json`](../../docs/specs/schemas/benchmark-project.schema.json));
the regression framework is [T04-02](../../docs/roadmap.json).

## Layout

| Path | Purpose |
|------|---------|
| `benchmarks/*.yaml` | Immutable benchmark project definitions (the corpus). |
| `ipermit_benchmarks/loader.py` | `load_benchmarks()` — parse + schema-validate. |
| `ipermit_benchmarks/runner.py` | `run_benchmarks()` — drive the engine, compare. |

## What the runner checks

For each benchmark, `run_benchmark` builds engine inputs and runs the
[T04-01 simulation engine](../../services/rules-engine/ipermit_engine/simulation.py),
then compares against the benchmark's expectations:

- `expected_outputs.permits` — exact set of (name, agency).
- `expected_confidence` — confidence tier per permit.
- `expected_known_unknowns` / `expected_advisories` — set membership (expected ⊆ actual).
- `expected_explanations` — fired `rule_id`, jurisdiction level, and a
  keyword-presence check on the trigger summary.

A benchmark whose `ruleset_version.content_hash` starts with `placeholder:` is
**skipped** (design-time stub), not failed — so the illustrative examples under
`docs/specs/examples/benchmarks/` remain valid without blocking CI.

## Engine inputs

Until the intake (T06-02) and GIS auto-detection (T05-03/T05-04) layers exist to
map raw project inputs to the engine's `project.*` / `geometry.* `/ `derived.*`
namespaces, each benchmark carries the engine-facing inputs explicitly under
`project_inputs.engine_context` and `project_inputs.applicable_jurisdiction_ids`
(allowed as additional properties by the schema). When those layers land, the
runner can derive context from the documented flat fields instead.

## Snapshot status

The seeded Texas rules (T02-06) are currently `status: draft` pending analyst
promotion ([T08-04](../../docs/roadmap.json)). The runner therefore evaluates the
full loaded rule snapshot (draft included) and each benchmark pins the snapshot's
`sha256:` content hash for provenance. Once rules are promoted to `effective`,
switch the runner to `governing_only` for true effective-date replay.

## Run it

```
python scripts/checks/run_regression.py   # prints passed/skipped/failed; non-zero on failure
pytest -q tests/benchmark/                 # same, as part of the suite
```
