# rules/

The declarative regulatory rule store. **This is data, not code** — rules are
editable without a deployment (AGENTS.md *Rules Engine Architecture*).

Every rule file conforms to the rule object schema
([`docs/specs/schemas/rule-object.schema.json`](../docs/specs/schemas/rule-object.schema.json), T00-01)
and is validated in CI (T01-07).

## Lifecycle directories

A rule's directory matches its `status` field. The four states and their
transitions are defined in [T00-03 Temporal Versioning](../docs/specs/temporal-versioning.md)
and AGENTS.md.

| Directory | State | Meaning |
|-----------|-------|---------|
| [`draft/`](./draft) | `draft` | Under development, not yet peer-reviewed. Not evaluated. |
| [`published/`](./published) | `published` | Reviewed and approved, but may be future-dated or pending activation. Not yet governing evaluations. |
| [`effective/`](./effective) | `effective` | Currently governs active evaluations. |
| [`archived/`](./archived) | `archived` | Superseded or expired, retained for historical replay. |

## Rules

- A rule moves between directories only through the publication workflow
  (T08-04), per the analyst SOP ([T00-09](../docs/specs/analyst-sop.md)).
- `published` ≠ `effective`: a rule may be approved and pre-staged with a future
  `effective_from`.
- Superseded rules may remain `effective` for grandfathered evaluations.
- **Never mutate `effective/` or `archived/` rules in place** — historical replay
  depends on their stability. Create a new version instead.

## Status

Scaffold only. Real Texas utility/transmission rules are seeded under T02-06.
