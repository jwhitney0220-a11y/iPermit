# packages/

Shared libraries consumed by `apps/` and `services/`.

| Package | Contents | Built by |
|---------|----------|----------|
| [`persistence/`](./persistence) | Shared SQLAlchemy declarative `Base`/metadata and engine/session factories used by all ORM model packages. | ADR-0005 → T02-01 |
| [`shared-schemas/`](./shared-schemas) | Canonical data models generated from `docs/specs/schemas/*.schema.json` — Pydantic models for Python services, TypeScript types for the apps. | T01-11 |
| [`jurisdiction-models/`](./jurisdiction-models) | Jurisdiction ORM models, canonical-record conversion/validation, alias support, and hierarchy traversal. | T00-08 spec → T02-01 |
| [`rule-definitions/`](./rule-definitions) | Rule object models, loaders, and validators against the rule-object schema. | T00-01 spec → T01-03 |
| [`benchmark-projects/`](./benchmark-projects) | Benchmark project definitions and loaders for regression testing. | T00-06 spec → T04-02 |

## Single source of truth

The JSON Schemas under [`docs/specs/schemas/`](../docs/specs/schemas) are
canonical. `shared-schemas` **generates** language-specific types from them — no
hand-written duplicates in Python or TypeScript. The codegen step is wired into
CI (T01-07 / T01-11) so client and server cannot drift. See
[ADR-0001](../docs/architecture/adr-0001-tech-stack.md).

## Status

Directory scaffold only.
