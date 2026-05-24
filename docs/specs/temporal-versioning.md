# Temporal Versioning Model

**Ticket:** T00-03
**Status:** Draft — pending peer review per T00-09 SOP
**Owner:** Product architecture
**Source guardrails:** [`/AGENTS.md`](../../AGENTS.md) sections *Temporal Versioning*, *Data Governance*, *Repository Strategy*, *Benchmark Project Library*
**Related tickets:** T00-01 (Rule Object), T00-06 (Benchmark Projects), T01-04 (Audit Logging), T03-02 (Rules Engine), T03-03 (Conflict Resolver), T08-04 (Publication Workflow)

---

## 1. Purpose

Defines the historical evaluation framework that lets the iPermit rules engine evaluate a project against the regulations that were *governing* on a specific date — not necessarily the regulations on disk today. This is the contract that makes audit replay, grandfathering, and reproducible permit matrices possible.

This spec is normative for any consumer of `rules/effective/` and for any system that persists evaluation results.

## 2. Non-Goals

This spec **does not** define:

- The rule object field shapes for `status`, `effective_from`, `effective_to`, `supersedes`, `superseded_by`. → **T00-01** (already on `main`). This spec consumes those fields; it does not redefine them.
- The runtime rules engine, its short-circuit logic, or its conflict resolver. → **T03-02** / **T03-03**.
- The audit log storage format, retention policy, or query API. → **T01-04**. This spec defines *what must be loggable*, not *how*.
- The on-disk directory layout (`rules/draft/`, `rules/published/`, `rules/effective/`, `rules/archived/`). → AGENTS.md *Repository Strategy*.
- The publication workflow that moves rule files between directories. → **T08-04**.
- The benchmark project format. → **T00-06**. This spec requires that benchmarks pin a `ruleset_version`; T00-06 owns the benchmark object shape.

Where another ticket owns a concept, this spec uses an opaque reference (e.g. `ruleset_version` is a content hash whose construction is defined here, but how it appears in benchmark objects is T00-06's call).

## 3. Conceptual Model — The Four Rule States

Per AGENTS.md *Temporal Versioning*, every rule object carries exactly one of four statuses. **Published rules are not necessarily effective rules.** The states are orthogonal to wall-clock time:

| State | Meaning | Governs live evaluations? | Available for replay? |
|-------|---------|----------------------------|------------------------|
| `draft` | Under analyst development; not yet peer-reviewed. | No | No |
| `published` | Approved by analyst review (T00-09); reviewer attribution exists; may have a future `effective_from`. | No | No |
| `effective` | Currently governing live evaluations. `effective_from` ≤ today and either `effective_to` is unset or ≥ today. | Yes | Yes |
| `archived` | Either explicitly superseded by a newer version, or `effective_to` has passed. Retained on disk for historical replay. | No | Yes |

### 3.1 The published-but-not-yet-effective case

A rule may sit in `rules/published/` with an `effective_from` in the future. Example: a county adopts an ordinance amendment on 2026-03-15 that takes effect 2026-07-01. The analyst publishes the new rule on 2026-03-20 with `effective_from: 2026-07-01`. Between 2026-03-20 and 2026-06-30, the rule is `published` but does not fire for any project evaluation. At 2026-07-01, the publication workflow (T08-04) atomically moves the file to `rules/effective/` and flips `status` to `effective`.

This is the property AGENTS.md calls out: *"A rule may be published before its effective date."* The engine never reads `rules/published/` during evaluation.

### 3.2 The superseded-but-still-governing case

A rule that is `effective` does not become `archived` the instant a newer version is published. It remains `effective` until either:

1. The newer version's `effective_from` is reached, **and** no grandfathered evaluations still reference it; or
2. Its own `effective_to` is reached.

In practice, the old version is moved to `rules/archived/` when the new version's `effective_from` is reached, but the historical replay machinery (§6) ensures grandfathered projects can still resolve it. Archive is a directory placement decision, not a deletion.

## 4. Selection Algorithm

Given an evaluation date `D` and the set of all rule files across `rules/effective/` and `rules/archived/`, the engine selects which version of each `rule_id` applies as follows:

```
For each distinct rule_id:
  candidates = all rule versions where:
    effective_from <= D
    AND (effective_to is unset OR effective_to >= D)
    AND status in {effective, archived}

  If candidates is empty:
    rule_id contributes nothing to this evaluation.

  If candidates has one entry:
    Use it.

  If candidates has multiple entries (overlapping effective windows):
    Choose the one with the latest effective_from.
    If still tied: choose the one with the highest semver `version`.
    If still tied: error — analyst SOP violation; raise.
```

### 4.1 What "evaluation date" means

The evaluation date `D` is **the project's pinned evaluation date**, not `now()`. Pinning rules:

1. **Default:** the date the consultant submits the project for evaluation (`project.submitted_at`, date portion, in the project's local timezone — Texas projects use `America/Chicago`).
2. **Override:** the consultant may select an alternative date in the intake form when one of these applies:
   - **Construction-start basis** — for projects where the consultant has reason to believe the regulation in force at construction start governs (e.g. a permit application filed under a prior ordinance grandfathered by §6).
   - **What-if exploration** — analyst tools allow selecting an arbitrary `D` for impact analysis. What-if evaluations are flagged `evaluation_mode = "exploratory"` and are not auditable as real evaluations.
3. **Replay:** for historical replay (§6), `D` is read from the persisted evaluation record. The user does not choose it.

The intake form (T06-02) is responsible for capturing the consultant's choice of basis. This spec only requires that *some* `D` is pinned to every evaluation record.

### 4.2 Worked example

Two versions of one rule:

| `rule_id@version` | `status` | `effective_from` | `effective_to` | `supersedes` |
|-------------------|----------|------------------|----------------|--------------|
| `tx-county-floodplain-development-permit@1.0.0` | archived | 2024-01-01 | 2025-12-31 | — |
| `tx-county-floodplain-development-permit@2.0.0` | effective | 2025-12-31 | — | `[tx-county-floodplain-development-permit@1.0.0]` |

Evaluation timeline:

- **Project A** submitted 2025-06-15 → `D = 2025-06-15`. v1.0.0 wins (only candidate: `2024-01-01 ≤ 2025-06-15 ≤ 2025-12-31`).
- **Project B** submitted 2026-02-10 → `D = 2026-02-10`. v2.0.0 wins (v1.0.0 excluded by `effective_to`).
- **Project C** submitted 2025-12-31 → `D = 2025-12-31`. Both versions match the window. Tie broken by latest `effective_from`: v2.0.0 wins.
- **Replay of Project A** run on 2026-08-04 → `D` is still `2025-06-15` (read from the persisted record). v1.0.0 still wins.

This is the property AGENTS.md calls out: *replays must reproduce the original outcome regardless of when the replay is executed.*

## 5. Grandfathering — Ruleset Version Pinning

Every evaluation MUST persist enough information that the *exact* set of rule files used to produce it can be reconstructed later. We call this the `ruleset_version`.

### 5.1 What gets pinned

A `ruleset_version` is a SHA-256 hash over a manifest of every rule file that was visible to the selection algorithm at evaluation time, namely the contents of `rules/effective/` and `rules/archived/`. Construction:

```
manifest = sorted list of (relative_path, sha256_of_file_contents)
           for every *.yaml and *.json file under rules/effective/ and rules/archived/
ruleset_version = sha256(canonical_json(manifest))
```

The manifest is itself persisted alongside the hash so that the hash can be verified and so that individual file contents can be retrieved without checking out an old git commit.

### 5.2 What gets stored on the evaluation record

Every persisted evaluation MUST carry:

| Field | Source | Required |
|-------|--------|----------|
| `evaluation_id` | engine | yes |
| `project_id` | intake | yes |
| `evaluation_date` (`D`) | intake or pin policy | yes |
| `evaluated_at` (wall-clock timestamp) | engine | yes |
| `ruleset_version` | engine | yes |
| `ruleset_manifest_ref` | engine | yes (pointer to the stored manifest) |
| `git_commit_sha` | engine | yes if rules are under git (recommended) |
| `engine_version` | engine | yes |
| `evaluation_mode` | intake | yes — one of `live`, `exploratory`, `replay` |

The audit log storage shape (`evaluation_id` → record mapping, retention, query) is owned by T01-04. This spec only mandates the fields.

### 5.3 Why a git SHA alone is not enough

Two reasons we hash the manifest separately:

1. **Working-copy drift.** A live evaluation may run against a working tree with uncommitted changes (e.g. mid-publication). The git SHA would be stale; the manifest hash is exact.
2. **Cross-repo or non-git deployments.** Production deployments may package `rules/effective/` into an immutable bundle and ship that without git history. The manifest hash is portable; the git SHA is not.

The git SHA is still recorded when available because it is the cheapest cross-reference for analysts.

### 5.4 Lock-in semantics

Once an evaluation record is written, its `ruleset_version` is immutable. A subsequent regulatory change does not retroactively alter the record. The consultant's permit matrix for that evaluation continues to reference v1.0.0 of the rule even after v2.0.0 becomes effective.

When the consultant requests a *re-evaluation*, the engine creates a **new** evaluation record with a new `ruleset_version`. Re-evaluation is an explicit action; it never happens silently.

## 6. Historical Replay

Replay is the operation: *given an old `evaluation_id`, reproduce its outputs exactly.*

### 6.1 Replay algorithm

```
1. Load the evaluation record by evaluation_id.
2. Read ruleset_version and ruleset_manifest_ref.
3. Reconstruct the rule file set from the stored manifest:
   - For each (path, sha) in the manifest, fetch the file content
     from the rule content store (T01-04 / T08-04).
   - Verify each file's sha matches.
4. Compute the manifest hash over the reconstructed set.
   - It MUST equal ruleset_version. Mismatch is a replay failure.
5. Load the project inputs snapshot referenced by the evaluation record
   (project inputs are also pinned; T06-02 owns the snapshot mechanism).
6. Invoke the rules engine with:
   - evaluation_date = D from the record
   - rule set = reconstructed files
   - project inputs = snapshot
   - engine_version = recorded value (may require running an older engine
     binary; see §6.2)
7. The new outputs MUST be byte-equal (after canonical serialization)
   to the originally recorded outputs.
```

### 6.2 Engine version compatibility

Replay reproducibility requires that the engine binary used for replay produces the same outputs as the binary used originally. T03-02 owns the engine. This spec imposes two requirements on T03-02:

1. **Determinism.** Given the same rule set, project inputs, and evaluation date, the engine MUST produce byte-equal outputs across runs.
2. **Versioned behavior.** Engine changes that alter output bytes (even for the same inputs) MUST bump `engine_version`. Replay against a different `engine_version` is permitted but MUST be flagged in the replay result as `engine_version_mismatch`.

### 6.3 Replay failure modes

The replay result is one of:

- `exact_match` — outputs are byte-equal. Audit succeeds.
- `engine_version_mismatch` — current engine differs from recorded engine; outputs may differ. Caller decides whether to accept.
- `manifest_unavailable` — one or more rule files in the manifest cannot be retrieved. Replay cannot proceed; this is a data-loss event and MUST be alerted on.
- `manifest_hash_mismatch` — retrieved files do not match recorded hashes. Indicates tampering or corruption; MUST be alerted on.

## 7. Audit Reproducibility Requirements

Every evaluation record, taken with the rule content store and the project inputs snapshot, MUST be sufficient to:

1. Re-run the evaluation and obtain the same outputs (`exact_match`).
2. Show the full set of rule files that were visible to the engine.
3. Show which rule versions fired and which did not, and why (the why is owned by T00-05 explainability output; this spec just requires the data is present).
4. Show the evaluator's pinned `evaluation_date` and pinning basis (`live` vs `exploratory` vs `replay`).

The audit log itself (storage, query, retention) is T01-04. This spec is the contract T01-04 must satisfy.

### 7.1 Tampering resistance

The manifest hash plus per-file hashes give detection (not prevention) of post-hoc rule edits. Prevention is a deployment concern (write-once content store, signed commits, etc.) and is out of scope here. T01-04 owns the storage hardening.

### 7.2 Retention

Evaluation records and their referenced manifests MUST be retained for the platform's full audit window. Specific retention duration is set by T01-04 and the data governance policy; this spec only mandates *non-deletion while the audit window is open*.

## 8. Cross-Ticket Deferrals

| Concern | Owner |
|---------|-------|
| `status`, `effective_from`, `effective_to`, `supersedes`, `superseded_by` field shapes | T00-01 (merged) |
| Engine implementation, short-circuit order, determinism guarantee | T03-02 |
| Rule-vs-rule conflict resolution within a single evaluation | T03-03 |
| Audit log storage, query API, retention enforcement | T01-04 |
| Rule directory layout (`rules/draft|published|effective|archived/`) | AGENTS.md *Repository Strategy* |
| Publication workflow (moves files between directories on `effective_from`) | T08-04 |
| Benchmark `historical rule version` field shape | T00-06 |
| Project inputs snapshot mechanism | T06-02 |
| Explainability output format | T00-05 |

## 9. Verification

This spec is verified when:

1. A reference implementation of the selection algorithm (§4) can be run against a fixture of rule files with overlapping effective windows and produces the expected version for each test `D`. Fixture lives under `tests/temporal-versioning/` (created by T03-02).
2. The worked example in §4.2 is encoded as a benchmark project under T00-06 (category: *temporal testing projects*, per AGENTS.md *Benchmark Project Library*).
3. The manifest hashing algorithm (§5.1) is implemented as a standalone utility and produces identical hashes across two independent runs on the same `rules/` tree.
4. A round-trip replay test exists: evaluate a project, persist the record, mutate `rules/effective/`, replay by `evaluation_id`, assert `exact_match`.
5. CI gates (T01-07) include schema validation of every rule file's lifecycle fields per T00-01's schema, plus a check that no rule in `rules/effective/` has `effective_from` in the future.

## 10. Change Control

Changes to this spec require:

1. PR review from at least one regulatory analyst (T00-09 SOP) and one engineer familiar with the rules engine.
2. If the manifest construction (§5.1) changes, all existing evaluation records' `ruleset_version` values become unverifiable under the new algorithm. Migration plan required: either re-hash historical manifests under both algorithms or version the hash construction itself (`ruleset_version_algo: "v1"` on the record).
3. If the selection algorithm (§4) changes, every persisted evaluation may produce different replay results. This is an audit-impacting change and requires explicit sign-off from the data governance owner.
