# Permit Dependency & Sequencing Model

**Ticket:** T00-04
**Status:** Draft — pending peer review per T00-09 SOP
**Owner:** Regulatory architecture
**Source guardrails:** [`/AGENTS.md`](../../AGENTS.md) sections *Rules Engine Architecture*, *Core Competitive Moats* (#2 "Workflow sequencing engine"), *Liability Strategy*, *MVP Functional Scope* ("sequencing guidance")
**Related tickets:** T00-01 (Rule Object, merged — owns `sequencing` field shape), T00-02 (Jurisdiction Ontology), T00-03 (Temporal Versioning), T00-05 (Explainability), T03-03 (Conflict Resolution), T03-04 (Sequencer Engine Implementation), T06-02 (Workflow UI), T07-01 (Permit Matrix Output)

---

## 1. Purpose

Defines the deterministic data model the iPermit workflow sequencing engine uses to convert a set of triggered rule objects into an ordered, parallelizable permit workflow.

Inputs to the model: the rule objects that fired for one project evaluation (each carrying the `sequencing` sub-object defined in T00-01 §5.7).

Outputs of the model: an ordered list of workflow stages, each containing one or more permits that may be pursued concurrently, annotated with critical-path and bottleneck flags.

This spec is normative for any consumer of `sequencing` data — including the engine (T03-04), the permit matrix exporter (T07-01), and the workflow UI (T06-02).

## 2. Non-Goals

This spec **does not** define:

- The on-disk shape of the `sequencing` sub-object. → **T00-01 §5.7** (already merged).
- The engine implementation that runs the algorithms described here. → **T03-04**.
- Conflict resolution between rules that produce contradictory outputs at the same jurisdiction level. → **T03-03**.
- The exported permit matrix file format (CSV/PDF/JSON layout). → **T07-01**.
- The visual rendering of stages, swimlanes, or Gantt-style displays. → **T06-02**.
- Cost estimation, scheduling math, or calendar-aware deadline projection.
- Live agency queue/backlog tracking. `typical_lead_time_days` is an advisory static estimate.

Where another ticket owns a concept, this spec uses an opaque reference (e.g. `rule_id` strings are validated by T00-01's schema; this spec only consumes them).

## 3. Design Principles (from AGENTS.md)

The dependency model MUST:

1. **Be deterministic.** The same set of fired rules and the same project context always produces the same stage ordering. No randomization, no time-of-day variance.
2. **Be advisory.** Outputs use AGENTS.md *Liability Strategy* language: "recommended workflow sequencing", "typical lead time", "likely bottleneck". Never "required order", "guaranteed timeline".
3. **Be explainable.** Every edge in the rendered dependency graph traces back to a specific field on a specific rule (`sequencing.prerequisites[]`, `sequencing.parallel_with[]`, or a `depends_on_response_from` entry — see §5.3).
4. **Be silent on absent prerequisites.** If a prerequisite rule did not fire for this project, the edge is dropped. The dependent permit is not blocked by a permit that does not apply (see §8).
5. **Be publication-gated.** Cycles in the dependency graph at the *ruleset* level are a publication-blocking validation error (see §6).

The model MUST NOT:

- Re-order permits in a way that contradicts an explicit `prerequisites` edge.
- Introduce ordering not declared in a rule's `sequencing` data. The model does not infer prerequisites from agency name, permit code, or jurisdiction level.
- Treat `parallel_with` as a hard constraint. It is advisory only (see §5.2).
- Collapse two rule_ids into one node, even if they describe the same agency permit at different jurisdiction versions. Temporal selection happens upstream (T00-03).

## 4. Conceptual Model

The dependency model is a **directed graph** `G = (V, E)` where:

- **V** (nodes) — one node per fired rule. The node identifier is the rule's `rule_id`. There is exactly one node per `rule_id` in any single evaluation (T00-03 has already selected the effective version, so version disambiguation is not the sequencer's concern).
- **E** (edges) — directed edges encoding three relationship kinds (§5).

Two graph scopes exist:

| Scope | Nodes | When evaluated | Cycle policy |
|-------|-------|----------------|--------------|
| **Ruleset graph** | Every published rule | At rule publication (T08-04) | Cycles are a publication-blocking error (§6). |
| **Project graph** | Only rules that fired for one evaluation | At evaluation time | Cycles are impossible if the ruleset graph is acyclic, because the project graph is a node-induced subgraph. The engine still re-checks defensively (§6). |

The model is fundamentally a permit-dependency DAG. The sequencing algorithm (§7) is a topological sort of the project graph; the bottleneck heuristic (§9) walks the resulting layered structure to identify critical-path permits with long lead times.

## 5. Edge Semantics

Three edge kinds carry distinct meanings. All three are *directed*. All three are sourced from a rule's `sequencing` sub-object (T00-01 §5.7) or a small companion structure (§5.3).

### 5.1 `prerequisite_of` — hard ordering

**Source field:** `sequencing.prerequisites[]` on rule `B` lists rule `A` ⇒ edge `A → B` of kind `prerequisite_of`.

**Semantics:** Permit `A` must be substantively complete before permit `B` is submitted. "Substantively complete" means: the agency action on `A` (issuance, determination, concurrence, or written response) has occurred. It does *not* require final certificate-in-hand if `B`'s agency accepts a pending-determination reference.

**Stage effect:** `B` is placed in a later stage than `A` (§7).

**Example:** USACE Jurisdictional Determination (JD) is a prerequisite of a CWA §404 application — the §404 PCN references the JD's wetland delineation.

### 5.2 `parallel_with` — advisory concurrency

**Source field:** `sequencing.parallel_with[]` on rule `A` lists rule `B` ⇒ undirected advisory edge `A — B` of kind `parallel_with`.

**Semantics:** Permits `A` and `B` can be pursued concurrently. This is a *hint* — the absence of a `parallel_with` edge does not forbid parallelism; the presence of one signals the analyst has confirmed no hidden serial dependency exists.

**Stage effect:** None directly. `parallel_with` does not place nodes in the same stage; topological sort does that automatically when no `prerequisite_of` edge separates them. The hint is preserved in the output for analyst-facing UI annotation (T06-02).

**Conflict:** If `A` declares `parallel_with: [B]` and either rule declares the other as a `prerequisite`, the `prerequisite_of` edge wins and the `parallel_with` claim is flagged as a contradictory advisory (validation warning, not error — §6).

### 5.3 `depends_on_response_from` — inter-agency response dependency

**Source field:** The base T00-01 `sequencing` sub-object does not carry inter-agency response edges natively. T00-04 introduces a companion *project-level* structure that the engine assembles from rule `prerequisites` plus the responding rule's `source_agency`:

When rule `A` is a `prerequisite_of` rule `B` and `A.source_agency != B.source_agency`, the resulting edge is automatically classified as kind `depends_on_response_from` (a subtype of `prerequisite_of`, not a replacement). This re-classification is purely a labeling concern for output and bottleneck analysis — the topological constraint is the same.

**Rationale:** Cross-agency response dependencies are the dominant source of real-world permitting delay. Surfacing them distinctly lets the matrix output (T07-01) and UI (T06-02) call out *"waiting on USACE response feeds TCEQ submission"* without analysts needing to manually tag every cross-agency edge.

**No new field required on rule objects.** Classification is computed at evaluation time from data already on the rule (`sequencing.prerequisites` + `source_agency`). T00-01's schema is not modified by this spec.

### 5.4 Edge kind summary

| Kind | Origin | Directional? | Topological effect | Bottleneck-relevant? |
|------|--------|-------------|--------------------|----------------------|
| `prerequisite_of` | `sequencing.prerequisites[]` | yes | forces later stage | yes |
| `depends_on_response_from` | `prerequisite_of` + cross-agency | yes | forces later stage | yes (priority) |
| `parallel_with` | `sequencing.parallel_with[]` | no (advisory) | none | no |

## 6. Graph Properties & Validation

### 6.1 DAG requirement

The ruleset dependency graph (considering only `prerequisite_of` edges; `parallel_with` edges are advisory and ignored for cycle detection) **MUST be acyclic**.

Cycle detection runs at rule publication time as part of the T08-04 publication workflow. Algorithm: Kahn's algorithm or Tarjan's SCC. Any strongly-connected component of size > 1, or any self-loop, is a publication-blocking error.

**Error surface:** the publication tool MUST list every cycle as a sequence of `rule_id`s (e.g. `a → b → c → a`) so the analyst can identify which `prerequisites[]` entry to remove.

### 6.2 Dangling prerequisite handling

A `sequencing.prerequisites[]` entry that references a non-existent or archived `rule_id` is a publication warning, not an error. Rationale: a prerequisite may legitimately reference a rule still in `draft/` during staged regulatory updates.

### 6.3 Project-level cycle defense

The project graph is a node-induced subgraph of the ruleset graph. If the ruleset graph is acyclic, the project graph is acyclic. The engine still runs cycle detection on the project graph as a defensive check; a cycle here is an engine bug, not a data problem, and surfaces as an internal error (not a user-facing message).

### 6.4 Other validations

- A rule MUST NOT list itself in `prerequisites` or `parallel_with`. Self-loops are a schema-level error.
- A rule MUST NOT list the same `rule_id` in both `prerequisites` and `parallel_with`. Contradictory; schema-level error.
- `parallel_with` is symmetric in intent but not enforced symmetric in storage. The engine treats it as symmetric: if `A` declares `parallel_with: [B]`, the edge applies regardless of whether `B` reciprocates. Analyst SOP (T00-09) will recommend reciprocal declaration for readability.

## 7. Sequencing Algorithm

The sequencer transforms the project graph into an ordered list of **stages**. Each stage is a set of `rule_id`s that share the same topological depth.

**Algorithm — layered topological sort (Kahn's variant):**

1. Build the project graph from fired rules: nodes = fired `rule_id`s; edges = `prerequisite_of` edges where *both* endpoints are fired rules. Drop any edge whose source rule did not fire (§8).
2. Compute in-degree for each node (count of incoming `prerequisite_of` edges).
3. Stage 0 = all nodes with in-degree 0.
4. For stage `n+1`: remove stage `n` nodes from the graph; recompute in-degrees; stage `n+1` = remaining nodes with in-degree 0.
5. Repeat until no nodes remain.

**Tie-breaking within a stage:** For deterministic output, sort stage members by `(jurisdiction_level_priority, source_agency, rule_id)` where `jurisdiction_level_priority` follows AGENTS.md jurisdiction hierarchy (federal first). This ordering is cosmetic — all members of a stage are concurrent — but it produces stable diffable output.

**Stage semantics:** Permits in the same stage may be pursued concurrently. Permits in stage `n+1` should not be submitted before all `prerequisite_of` predecessors in stages `0..n` are substantively complete.

**Complexity:** O(V + E). The largest expected project graph (Texas multi-county linear utility crossing federal jurisdiction) is well under 100 nodes; performance is not a concern.

## 8. Skipped-Prerequisite Rule

If rule `A` is declared as a `prerequisite_of` rule `B`, but rule `A` did not fire for this project, the dependency edge is **silently dropped**.

**Rationale:** If `A` doesn't apply to this project, it can't be a blocker. Forcing the consultant to satisfy an inapplicable permit would contradict AGENTS.md *Liability Strategy* ("recommended workflow sequencing", not invented obligations).

**No advisory is emitted** for routinely skipped prerequisites (e.g. a state permit is prerequisite for a county permit, but the state permit didn't trigger because the project is below the state threshold). Surfacing this would produce noisy advisories on most projects.

**Exception — analyst opt-in flag (future):** A future enhancement may allow a rule to mark a prerequisite as "always advise even if skipped" for rare cases where consultants commonly miss a triggering condition. This is out of scope for T00-04 and will be picked up in a follow-up ticket if analyst feedback indicates need.

## 9. Bottleneck & Critical Path Identification

### 9.1 Critical path

The critical path of the project graph is the longest path (by `typical_lead_time_days` weight) from any stage-0 node to any terminal node, using `prerequisite_of` edges only.

Algorithm: standard longest-path-in-DAG via topological order. Linear in V + E.

**Node weight:** `sequencing.typical_lead_time_days` if present, else 0.

**Output:** The set of `rule_id`s on the critical path is annotated in the sequencer output. Multiple equal-length critical paths are all reported.

### 9.2 Bottleneck threshold

A permit is flagged as a **bottleneck** when both:

1. It lies on the critical path, AND
2. Its `typical_lead_time_days` is `>= 120` (default threshold).

The threshold value is a configuration constant of the sequencer (T03-04), not a per-rule field. The 120-day default is sourced from common Texas USACE individual permit timelines; analyst review may tune it. Configuration is project-wide, not per-rule.

### 9.3 Cross-agency response bottleneck priority

Bottlenecks where the incoming edge is `depends_on_response_from` are tagged with a `cross_agency_response` flag in the output. This is the highest-priority bottleneck class for consultant-facing display per AGENTS.md *MVP Functional Scope* output requirements.

### 9.4 Bottleneck output

Per bottleneck, the sequencer emits:

- `rule_id`
- `permit_name` (copied from rule output)
- `typical_lead_time_days`
- `cross_agency_response: bool`
- `predecessors`: list of `rule_id`s that feed into this bottleneck
- `successors`: list of `rule_id`s blocked by this bottleneck

The exact serialization is owned by T07-01.

## 10. Worked Example — Texas Transmission Wetland Crossing

**Project:** 12-mile 138 kV transmission line in a single Texas county. Route crosses one perennial stream and one mapped wetland (USACE jurisdictional). Project disturbs > 1 acre. County has an adopted floodplain ordinance.

**Fired rules (illustrative `rule_id`s):**

| rule_id | permit | agency | typical_lead_time_days |
|---------|--------|--------|------------------------|
| `us-usace-jurisdictional-determination` | Approved JD | USACE | 90 |
| `us-usace-section-404-nationwide-permit` | CWA §404 NWP / PCN | USACE | 60 |
| `tx-tceq-401-water-quality-certification` | §401 WQC | TCEQ | 60 |
| `tx-tceq-tpdes-construction-stormwater` | TPDES CGP NOI | TCEQ | 14 |
| `tx-county-floodplain-development-permit` | County floodplain permit | County floodplain admin | 30 |

**Declared `sequencing` on each rule:**

- `us-usace-section-404-nationwide-permit.prerequisites = ["us-usace-jurisdictional-determination"]`
- `tx-tceq-401-water-quality-certification.prerequisites = ["us-usace-section-404-nationwide-permit"]`
- `tx-tceq-tpdes-construction-stormwater.parallel_with = ["us-usace-section-404-nationwide-permit", "tx-county-floodplain-development-permit"]`
- `tx-county-floodplain-development-permit.parallel_with = ["tx-tceq-tpdes-construction-stormwater"]`

**Edge classification:**

- `JD → §404`: `prerequisite_of` (same agency, USACE).
- `§404 → §401 WQC`: `depends_on_response_from` (cross-agency, USACE → TCEQ).
- TPDES, county floodplain: no prerequisites among fired rules.

**Layered topological sort:**

| Stage | Permits | Notes |
|-------|---------|-------|
| **Stage 0** | USACE JD, TPDES CGP NOI, County floodplain permit | No predecessors among fired rules. Three parallel tracks open immediately. |
| **Stage 1** | CWA §404 NWP / PCN | Waits on JD. |
| **Stage 2** | §401 WQC | Waits on §404 (cross-agency response edge). |

**Critical path:** JD (90) → §404 (60) → §401 WQC (60) = **210 days**.

**Bottlenecks (threshold 120, on critical path):** none of the individual nodes exceed 120 days alone, so under the default threshold no single node is flagged. The sequencer still reports the 210-day critical path as the project's headline lead-time figure, and tags the `§404 → §401 WQC` edge as `cross_agency_response` for analyst attention.

**If the project instead required a USACE Individual Permit** (`typical_lead_time_days: 365`), that node would exceed the 120-day threshold and would be emitted as a `cross_agency_response` bottleneck since downstream §401 WQC depends on its issuance.

**Parallelism callout for consultant output:** TPDES CGP NOI (14 days) and County floodplain permit (30 days) are entirely off the critical path and should be initiated on day 1.

## 11. Output Contract

The sequencer's output, consumed by T07-01 (permit matrix) and T06-02 (workflow UI), conceptually contains:

- `stages`: ordered array. Each stage carries `stage_index` and `permits[]` (each entry: `rule_id`, `permit_name`, `source_agency`, `typical_lead_time_days`, `on_critical_path: bool`).
- `critical_path`: ordered array of `rule_id`s.
- `critical_path_total_days`: integer sum of `typical_lead_time_days` on the path.
- `bottlenecks`: array per §9.4.
- `parallel_with_hints`: array of `[rule_id_a, rule_id_b]` pairs preserved from rule declarations for UI display.
- `dropped_edges`: array of skipped-prerequisite entries (predecessor rule_id, successor rule_id, reason `prerequisite_not_triggered`). For analyst debug; not surfaced to consultants by default.

The exact JSON/CSV/PDF serialization is owned by **T07-01**. This spec defines the conceptual contract only.

## 12. Open Questions Deferred to Other Tickets

- **Bottleneck threshold tuning** — 120 days is a default; analyst SOP (T00-09) may publish a tuning guide once benchmarks (T00-06) accumulate.
- **Calendar-aware projection** — converting lead-time-days into projected submission/approval dates requires holiday and working-day handling; out of scope here, picked up if/when a scheduling feature is greenlit.
- **Per-rule prerequisite advisories on skip** — see §8 "Exception".
- **`parallel_with` symmetry enforcement** — analyst SOP recommendation only; not enforced in schema.
- **Agency queue/backlog signals** — live agency processing-time data is a much later (post-MVP) input; the model treats `typical_lead_time_days` as static and rule-declared.

## 13. Change Control

Changes to this spec require:

1. PR review from at least one regulatory analyst (T00-09 SOP) and one engineer who has read T03-04 (engine implementation).
2. Coordination with T00-01 owners if any change implies a new field on the rule object's `sequencing` sub-object. T00-04 does not modify the T00-01 schema; any future need to do so requires an explicit T00-01 amendment.
3. Re-validation of cycle-detection behavior against the benchmark project library (T00-06) when the algorithm or thresholds change.
