# tests/

Cross-cutting and integration tests that span multiple services or packages.
Unit tests live alongside the code they cover, inside each service/package.

Key suites that will land here:

- **Schema validation** — every rule, jurisdiction record, and benchmark validates
  against its JSON Schema (T01-07 wires this into CI).
- **Benchmark regression** — evaluate benchmark projects ([T00-06](../docs/specs/benchmarks.md))
  against the rules engine and assert stable outputs (T04-02).

## Status

Directory scaffold only. Test runners are configured in T01-12; CI in T01-07.
