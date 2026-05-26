---
name: saas-api
description: Use when building or changing the iPermit FastAPI REST surface — routers, endpoints, the response envelope, OpenAPI contract, API versioning, or error handling. Triggers on work in services/api/ipermit_api or any HTTP boundary exposing the rules engine / GIS / permit matrix.
---

# saas-api — iPermit REST surface

**Authority:** `docs/architecture/adr-0003-api-contract-and-surface.md`. Read it first; it is the contract, not a suggestion.

## Conventions (ADR-0003)
- REST over HTTP via FastAPI, under `/api/v1/...`; changes within a major version must be additive.
- The auto-generated OpenAPI doc IS the published contract and feeds the TypeScript client codegen.
- Response envelope: `{ data, meta, advisories[], warnings[] }`. `meta` carries `ruleset_version`, `evaluation_date`, `evaluation_id`, `schema_version`.
- **A permit response with zero advisories is a contract violation** (liability framework, T07-03) — always include the platform advisory.
- Errors use RFC-9457 problem-details (`type`, `title`, `status`, `detail`, `instance`, `errors?[]`).

## Reuse (don't rebuild)
- Evaluation: `ipermit_engine.simulate_project` (services/rules-engine).
- GIS → engine inputs: `ipermit_gis.confirm_detection` / `to_engine_inputs`.
- Rules snapshot: `ipermit_rules.load_rules`.
- DB session: `ipermit_persistence.make_session_factory`.

## Guardrails
- Functions ≤ 60 body lines (`scripts/checks/check_function_length.py`).
- Any NEW domain output shape gets a `docs/specs/schemas/*.schema.json` + example registered in `scripts/checks/validate_schemas.py` (API envelope models stay Pydantic-only per ADR-0003).
- Run the **code-review** skill on the diff; run **security-review** if the change touches auth/tenancy.

## Verify
`uvicorn ipermit_api.app:app` boots; `/openapi.json` and `/docs` render; pytest with `httpx` exercises the endpoints.
