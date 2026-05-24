# 02 — Repository Strategy

**Status:** Authored
**Source guardrails:** [`AGENTS.md`](../../AGENTS.md) sections *Repository Strategy*, *Temporal Versioning*, *Rules Engine Architecture*
**Related tickets:** T00-07 (this handbook), T01-05 (monorepo init), T01-03 (declarative rules repo), T01-06 (branching), T08-04 (publication workflow)

---

## 1. Why a Monorepo

`AGENTS.md` *Repository Strategy* mandates a monorepo until a future architecture review proves otherwise. The reason is direct: iPermit's value chain is tightly coupled. A rule object change touches the rules engine, the shared schema package, the benchmark project library, and the consultant-facing permit matrix. Coordinating those across multiple repos would slow every analyst-driven change to a crawl.

If you find yourself wishing for a split repo, you are probably wishing for a clearer module boundary inside the monorepo. Add the boundary first; revisit splitting only if the boundary holds for at least one full release cycle.

## 2. Top-Level Layout

The canonical layout (per `AGENTS.md` and T01-05) is:

```
/apps
  /web                 ← consultant-facing frontend (T06-01)
  /analyst-portal      ← internal frontend for analysts and admins (T08-02)

/services
  /rules-engine        ← deterministic evaluator (EPIC-03)
  /gis-engine          ← spatial overlay services (EPIC-05)
  /ai-assistant        ← constrained AI tooling (EPIC-09)
  /regulatory-monitor  ← source-monitoring jobs (T08-03, T09-04)

/packages
  /shared-schemas      ← cross-service types (T01-11)
  /jurisdiction-models ← jurisdiction ontology (T00-02, T02-01)
  /rule-definitions    ← rule-object types and validators
  /benchmark-projects  ← benchmark fixtures (T00-06)

/rules
  /draft               ← under development, not yet reviewed
  /published           ← approved, may be future-dated
  /effective           ← currently governing evaluations
  /archived            ← superseded or expired

/infrastructure         ← IaC (T01-09)
/docs                   ← architecture, specs, handbook, roadmap
/scripts                ← developer and ops scripts (T01-12)
/tests                  ← cross-service integration tests
```

Most of these directories do not exist yet. They are created as their owning tickets ship. Add a directory only when you are landing the ticket that owns it; do not pre-create empty trees.

## 3. The Four-Stage `rules/` Directory

`rules/` has four subdirectories — `draft/`, `published/`, `effective/`, `archived/` — because a rule's *publication state* and its *temporal effectiveness* are independent dimensions. From `AGENTS.md` *Temporal Versioning*:

| Directory | Meaning | Who edits it |
|-----------|---------|--------------|
| `draft/` | Analyst is still writing or revising. Not reviewed. May fail schema validation in progress. | Authoring analyst, on a feature branch. |
| `published/` | Reviewed, approved, but not yet governing evaluations. May be staged ahead of a future regulatory change. | Publication workflow (T08-04). Engineering PRs MUST NOT move files into here. |
| `effective/` | Currently governs evaluations. The engine reads from here. | Publication workflow (T08-04), automatically as `effective_from` passes. |
| `archived/` | Superseded or expired. Retained for historical replay and grandfathered evaluations. | Publication workflow, automatically as `effective_to` passes or `superseded_by` is set. |

A rule MUST live in the directory matching its `status` field (per `docs/specs/rule-object.md` §5.4). The two are kept in sync by the publication workflow; do not edit one without the other.

### Why four and not three?

A common mistake is collapsing `published` into `effective`. They are different:

- A rule may be **published** in February to take effect in July when a new ordinance kicks in. Until July, it should not influence any project evaluation.
- A rule may be **superseded** by a newer version but remain **effective** for grandfathered evaluations of older projects. The newer version is `effective` for new projects; the older is `archived` but still loadable for historical replay.

The directory layout makes both cases physically obvious. You can `ls rules/effective/` and know exactly what the engine sees today.

## 4. PR Flow

The PR flow depends on what the PR touches.

### Engineering-only PR (code under `apps/`, `services/`, `packages/`, etc.)

1. Branch from `main` (per T01-06 branching strategy, once shipped; until then, `main` is the default base).
2. Implement, keeping every function under 60 lines (see [01-engineering-standards](./01-engineering-standards.md)).
3. Update tests under `tests/` or the service's local test dir.
4. Open a PR. CI (T01-07, once shipped) runs lint, function-length check, schema validation, and unit tests.
5. Get review from a code owner. Merge.

### Rule authoring PR (files under `rules/draft/` only)

1. Analyst branches from `main`.
2. Creates or edits a YAML file under `rules/draft/`.
3. Validates locally against `docs/specs/schemas/rule-object.schema.json` (procedure in [05-editing-rules-safely](./05-editing-rules-safely.md)).
4. Opens a PR. CI validates the schema and runs benchmark tests against the *draft* set (once T04-02 ships).
5. Engineering review confirms schema validity; analyst peer review (T00-09) confirms regulatory accuracy.
6. Merge into `main`. The file remains in `draft/`.

### Publication PR (moves a rule from `draft/` to `published/`, or `published/` to `effective/`)

This flow is owned by T08-04 and is **not** done by hand. Until T08-04 ships, treat any file in `published/` or `effective/` as immutable. If you need to change one, file an analyst ticket; do not edit it directly.

### Mixed PRs

Avoid them. A PR that ships both engine code and a rule change makes review and rollback harder. If you genuinely need both, split into two PRs and merge in order: code first, then rules.

## 5. Branch Protection

Per `AGENTS.md` *Repository Strategy*, the repository must protect:

- `main` — no direct pushes; PR required.
- `rules/published/` and `rules/effective/` — only the publication workflow may write here (enforced by CODEOWNERS once T01-13 ships).
- Production deployment branches — release tags only, no force-push.

Until those protections are codified in `.github/`, they are review expectations. Reviewers should reject any PR that writes to `rules/published/` or `rules/effective/` outside the publication workflow.

## 6. Multi-State Future-Proofing

`AGENTS.md` *Geographic Scope* requires that the architecture support future expansion to additional states. The repository strategy supports this by:

- Keeping jurisdiction data in `packages/jurisdiction-models/`, not embedded in service code.
- Keeping rules in flat per-state-agnostic YAML, with `jurisdiction_id` as the only state identifier.
- Avoiding any directory like `rules/texas/` that would require a directory move when a second state is added. State is a property of the rule's `jurisdiction_id`, not its file path.

When a second state ships, no directory restructure should be needed. If you find yourself wanting one, raise it in the EPIC-00 architecture discussion before acting.

## 7. What to Do When the Layout Doesn't Yet Exist

Most of this is not yet on disk. If your ticket needs a directory that the canonical layout calls for, but that directory does not exist:

1. Confirm the canonical name in this document and in `AGENTS.md`.
2. Create only the directories your ticket genuinely needs — do not pre-create empty service skeletons.
3. Add a one-line note in your PR description: *"Creates `services/rules-engine/` per AGENTS.md *Repository Strategy*; owned by T03-01."*
4. If your ticket is the one that creates the directory (e.g. T01-05 monorepo init), this handbook section should be updated to remove the "does not exist yet" caveat in the same PR.
