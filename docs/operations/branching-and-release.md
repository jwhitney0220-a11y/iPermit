# Branching and Release Strategy

**Ticket:** T01-06 (branching strategy)
**Related:** T01-01 (repository governance), T01-07 (CI pipelines), T01-09 (infra/staging), T08-04 (publication workflow), T00-09 (analyst SOP)
**Source guardrails:** [`/AGENTS.md`](../../AGENTS.md) *Repository Strategy*, *Temporal Versioning*, *Human Review Workflow*
**See also:** [`docs/engineering-handbook/02-repository-strategy.md`](../engineering-handbook/02-repository-strategy.md)

This document defines how branches flow, how releases are cut, and what must be
protected. Branch-protection rules are codified in repository settings; this doc
states the *intent* a reviewer or admin enforces. CI enforcement is owned by
T01-07; infrastructure and staging environments by T01-09.

---

## 1. Long-Lived Branches

| Branch | Purpose | Direct pushes |
|--------|---------|---------------|
| `main` | Always-deployable trunk. The base every feature branches from and merges back into. Tagged for production releases. | Forbidden. PR + review only. |
| `develop` | Optional integration branch used only when a release needs to stabilize multiple in-flight features before cutting from `main`. Not required for routine single-PR work. | Forbidden. PR only. |

`main` is the single source of truth. For most of the MVP, work branches from
`main` and merges back to `main`. `develop` exists for the cases where a batch of
features must be integrated and soak-tested together before a release; if you do
not have that need, do not use it.

## 2. Short-Lived Branches

| Prefix | Use | Base | Example |
|--------|-----|------|---------|
| `feature/<ticket>-<slug>` | New work for a roadmap ticket. | `main` (or `develop` during a stabilizing release) | `feature/t01-06-branching-strategy` |
| `fix/<ticket>-<slug>` | Non-urgent bug fix. | `main` | `fix/t03-02-threshold-rounding` |
| `analyst/<rule-id>-<version>` | Regulatory rule authoring in `rules/draft/`. Defined by the analyst SOP (T00-09 §4.1). | `main` | `analyst/tx-travis-floodplain-development-permit-1.0.0` |
| `release/<version>` | Release stabilization. Only docs, version bumps, and fixes land here. | `main` (or `develop`) | `release/0.2.0` |
| `hotfix/<version>-<slug>` | Urgent production fix that cannot wait for the normal cycle. | the release tag on `main` | `hotfix/0.1.1-export-crash` |
| `claude/<topic>` | Agent-authored branches. Permitted and already in use; treat them like `feature/` branches for review. | `main` | `claude/t01-governance` |

Naming conventions:

- Lowercase, hyphen-separated. Lead with the ticket ID where one exists so the
  branch traces to the roadmap.
- Keep slugs short and descriptive of the change, not the file.
- One ticket per branch where practical. Do not mix engine code and rule changes
  on the same branch (see §6).

## 3. Feature Flow

1. Branch from `main`: `git checkout -b feature/<ticket>-<slug>`.
2. Implement. Keep every function under 60 lines (T01-02, AGENTS.md *Engineering
   Standards*).
3. Push and open a PR targeting `main`.
4. CI (T01-07) runs lint, function-length check, schema validation, and tests.
5. At least one code-owner review approves (§7). Merge by squash unless the commit
   history is intentionally meaningful.
6. Delete the branch after merge.

## 4. Release Flow

1. Cut `release/<version>` from `main` (or `develop` if a stabilizing integration
   branch was used).
2. Only stabilization changes land on the release branch: version bumps,
   changelog, documentation, and fixes for issues found during release testing.
   No new features.
3. When green on staging (T01-09), merge the release branch back to `main` and tag
   the merge commit: `git tag -a v<version> -m "Release <version>"`.
4. The tag — not a branch — is the production deploy artifact. Production deploys
   from tags only (§5).
5. If `develop` was used, merge the release back into `develop` as well so it does
   not fall behind.

Versioning follows semver at the repository level. Rule-object versioning is
separate and owned by the analyst SOP (T00-09 §3.5).

## 5. Hotfix Flow

1. Branch `hotfix/<version>-<slug>` from the production tag on `main`.
2. Fix the issue, keeping the change minimal.
3. PR into `main` with expedited but still mandatory review (§7).
4. Tag a patch release (e.g. `v0.1.1`) on the merge commit and deploy from the tag.
5. Forward-port the fix to `develop` if it exists so the next release keeps it.

A hotfix never bypasses review or CI. It compresses turnaround, not gates.

## 6. Rule Changes Are Not Ordinary Code Changes

Rule data under `rules/` follows a different path from engine code. The full
procedure is the analyst SOP (T00-09); the repository-level rules are:

- Rule *authoring* happens on `analyst/<rule-id>-<version>` branches and lands in
  `rules/draft/` only.
- Moving a file into `rules/published/` or `rules/effective/` is a **publication**
  action owned by the publication workflow (T08-04) and gated by analyst sign-off.
  It is never a routine engineering merge.
- Do not mix a rule change and engine code on one PR. Split them and merge code
  first, then rules (see [repository strategy §4](../engineering-handbook/02-repository-strategy.md)).

## 7. Code-Review Standards

- Every PR needs at least one approving review from a code owner (CODEOWNERS,
  `.github/CODEOWNERS`).
- **Rule changes additionally require a regulatory-analyst reviewer** who is not
  the drafting analyst (T00-09 §1, §7). Engineering review confirms schema
  validity; analyst peer review confirms regulatory accuracy.
- Reviewers reject any PR that:
  - writes to `rules/published/` or `rules/effective/` outside the publication
    workflow,
  - introduces a function over 60 lines,
  - adds authoritative or guarantee-style language to consultant-facing output
    (AGENTS.md *Liability Strategy*; SOP §5.1).
- Stale approvals do not carry across new commits on rule PRs (T00-09 §6.4). Push
  after approval requires re-review.

## 8. Branch Protection Intent

These are the protections an admin configures in repository settings and that
reviewers uphold until they are fully codified.

### 8.1 Protect `main`

- No direct pushes; PR required.
- At least one approving review from a code owner before merge.
- Required status checks (T01-07) must pass: lint, function-length, schema
  validation, tests.
- No force-push, no branch deletion.

### 8.2 Protect production deploys

- Production deploys from version tags only, never from an arbitrary branch.
- Release and hotfix tags are not force-moved.
- Deploy approval gating is owned by T01-09 infrastructure.

### 8.3 Protect published and effective rules

Per AGENTS.md *Repository Strategy* — published rules must not be edited without
analyst approval:

- `rules/published/` and `rules/effective/` are writable only through the
  publication workflow (T08-04). CODEOWNERS routes any change in these paths to the
  regulatory-analyst group for required review.
- The publication workflow itself (the tooling and CI that performs the
  `draft → published → effective` move, T08-04) is protected: changes to it require
  both an engineering owner and a regulatory-analyst owner.
- Files under `rules/effective/` and `rules/archived/` are immutable in content.
  A change is a new version plus a transition (T00-09 §9), never an in-place edit.
- Until these protections are fully codified in repository settings and CI,
  reviewers enforce them by rejecting non-conforming PRs.

## 9. Multi-State Future-Proofing

Branch and release naming carries no state identifier. State is a property of a
rule's `jurisdiction_id`, not a branch or a directory
(see [repository strategy §6](../engineering-handbook/02-repository-strategy.md)).
Adding a second state requires no new branch convention.
