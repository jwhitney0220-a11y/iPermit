# 06 — Testing and QA/QC

**Status:** Partial — schema-validation and benchmark guidance authored; regression, simulation, and diff frameworks pending EPIC-04
**Source guardrails:** [`AGENTS.md`](../../AGENTS.md) sections *Benchmark Project Library*, *Human Review Workflow*
**Related tickets:** T00-01 (rule object spec — shipped), T00-06 (benchmark suite), T04-01 (simulation), T04-02 (regression), T04-03 (edge cases), T04-04 (rule diff), T04-05 (QA dashboard)

---

## 1. The Two Testing Surfaces

iPermit has two testing surfaces with different cultures and tools:

1. **Engineering tests.** Unit and integration tests for code under `apps/`, `services/`, and `packages/`. Run on every PR by CI (T01-07). Standard Python/JS/TS testing tools.
2. **Regulatory tests.** Benchmark projects that exercise the rules engine against known-good outputs. Owned by the analyst team. Run by T04-02 once it ships.

Both must pass before a PR merges. Both must pass before a deployment goes out. Treat the regulatory surface with at least as much rigor as the engineering surface — the platform's promise is *deterministic, explainable permit evaluation*, and the benchmark suite is the only thing that can prove the determinism part.

## 2. What You Can Test Today

Until EPIC-04 ships, the executable testing surface is small. You can:

- **Validate rule files against the JSON Schema** from T00-01. Procedure in [05-editing-rules-safely](./05-editing-rules-safely.md) §3. This catches structural errors but not semantic ones.
- **Validate the example rule object** at `docs/specs/examples/rule-object-example.json` against the same schema. This is wired into CI under T01-07 once that ships; until then, run it locally.
- **Hand-trace a benchmark project's expected outputs** against any draft rule you have written, on paper. This is not automated. It is still useful — most rule bugs are findable by reading the rule and the benchmark side by side.

You cannot yet:

- Run benchmark projects through an executable rules engine. The engine (EPIC-03) and the regression framework (T04-02) are both unbuilt.
- Run rule diffs across versions (T04-04, unbuilt).
- Simulate hypothetical rule changes (T04-01, unbuilt).

## 3. Benchmark Projects

Per `AGENTS.md` *Benchmark Project Library*, benchmark projects are core production infrastructure, not an afterthought. They are the only assertion that engine behavior is stable over time.

### 3.1 What a benchmark project is

A frozen project input plus its expected outputs at a specific historical rule version. From `AGENTS.md`, each benchmark must include:

- benchmark ID
- project inputs
- expected outputs
- expected confidence
- expected explanations
- expected known unknowns
- historical rule version

### 3.2 What benchmarks are for

- **Regression detection.** A change to engine code or to an effective rule should not silently change a benchmark's output. If it does, the change is either intentional (and the benchmark must be re-frozen with a documented reason) or it is a regression.
- **Edge-case coverage.** The required benchmark categories from `AGENTS.md` (simple linear, multi-county, federal nexus, conflicting jurisdictions, temporal cases, known unknowns) collectively cover the engine's hardest paths.
- **Explainability verification.** A benchmark asserts on the *explanation* the engine generates, not just the permit list. An engine that produces the right permits with the wrong reasons is broken.

### 3.3 What benchmarks are NOT for

- They are NOT for proving regulatory correctness. A benchmark says "given these rules, the engine produces these outputs." It does not say "these outputs are legally correct." Legal correctness is the analyst team's responsibility.
- They are NOT a substitute for the analyst review workflow. A rule change can pass every benchmark and still be wrong if it misreads the underlying regulation.

### 3.4 Adding a benchmark today

T00-06 owns the benchmark format and the initial fixtures. Until T00-06 ships:

- Sketch benchmark scenarios in PR descriptions when you author a draft rule. State the inputs and expected outputs in plain English.
- Save these sketches; they will be the seed material for the T00-06 fixtures.

## 4. Schema Validation in CI

T01-07 wires schema validation into CI. The expected behavior:

- Every file in `rules/draft/`, `rules/published/`, `rules/effective/`, and `rules/archived/` is loaded and validated against `docs/specs/schemas/rule-object.schema.json`.
- Any failure blocks the PR.
- The example rule at `docs/specs/examples/rule-object-example.json` is validated to catch schema regressions.

Until T01-07 ships, this is a manual gate. Reviewers should run the validator (procedure in [05-editing-rules-safely](./05-editing-rules-safely.md) §3) against any changed rule file before approving.

## 5. Required QA/QC Steps Before Deployment

`AGENTS.md` *Engineering Handbook Requirement* requires this section to document required QA/QC steps. The current authoritative list is:

1. **All schema validation passes.** Every rule file in the repository is valid against the rule-object schema.
2. **All engineering unit tests pass.**
3. **All benchmark projects produce their expected outputs** — once T04-02 has shipped. Until then, this step is "no regression detected by hand-tracing the benchmarks affected by the change."
4. **Every changed rule file is in `draft/`** unless the change is going through the T08-04 publication workflow.
5. **No `published/` or `effective/` file changed outside the publication workflow.**
6. **Reviewer attribution exists** on any rule destined for `published/` or `effective/`.

Items 3 and 5 will become CI-enforced as T04-02 and T08-04 ship. Until then, they are reviewer expectations.

## 6. Regression, Simulation, and Diff

**[Pending: filled when EPIC-04 ships. Owner: T04-01 + T04-02 + T04-04]**

The regression framework (T04-02), the simulation engine (T04-01), and the rule diff tooling (T04-04) together will define how engineers and analysts confirm a change is safe before it ships. This section will explain:

- How to run the regression suite locally and in CI.
- How to interpret a regression failure (engine bug? rule bug? benchmark bug?).
- How to simulate a hypothetical rule change against the active ruleset before publishing.
- How to read a rule diff between two versions of the same `rule_id`.

**Consult instead:**

- [`AGENTS.md`](../../AGENTS.md) *Benchmark Project Library*.
- [`docs/roadmap.md`](../roadmap.md) EPIC-04 ticket descriptions.
- [`docs/specs/rule-object.md`](../specs/rule-object.md) §11, which calls out rule diffing as deferred to T04-04.

When those tickets ship, the authors should replace the *Pending* line above with the concrete procedures and update the handbook [README](./README.md) table of contents.
