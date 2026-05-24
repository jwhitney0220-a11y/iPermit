# iPermit Development Roadmap

> **Source of truth:** [`docs/roadmap.json`](./roadmap.json) (version: `merged-final-v2`, updated: 2026-05-24)
> **Strategic guardrails:** [`AGENTS.md`](../AGENTS.md)

This document is a human-readable rendering of `roadmap.json`. If the two
diverge, the JSON wins. Update the JSON first, then regenerate this view.

---

## Revision Notes (`merged-final-v2`)

- Incorporated expanded EPIC-00 tickets (T00-08 Jurisdiction Naming Standard, T00-09 Analyst SOP Manual) from updated submission.
- Incorporated expanded EPIC-01 engineering bootstrap tickets (T01-05 through T01-13) from updated submission.
- Moved Dataset Seeding & Ingestion Playbook from EPIC-08 to EPIC-02 (now T02-06) so real Texas data is available before rules engine and benchmark testing begin.
- Added Auth, RBAC & Tenant Isolation (T01-14) to EPIC-01 to support multi-user consultant and enterprise workflows.
- Added API Contract & Surface Design (T01-15) to EPIC-01 to formalize the boundary between rules engine and frontend/export layers.
- Added PostGIS & Spatial Infrastructure Planning (T01-16) to EPIC-01 so hosting and CI/CD decisions account for spatial DB requirements before EPIC-05.
- Added Consultant Frontend Shell & Navigation (T06-01) to EPIC-06; existing tickets renumbered T06-02 through T06-04.
- Added Internal Frontend Shell & Admin Navigation (T08-02) to EPIC-08; existing tickets renumbered accordingly.
- Added explicit dependency chains linking T00-06 → T02-06 → T04-02 and T01-16 → T05-01.
- Updated deferred list to include items present in AGENTS.md but missing from prior JSON versions.
- Added `/effective` rules directory to T01-05 monorepo structure, distinguishing published from currently-effective rules.
- Added Data Freshness Scoring (T02-07) to EPIC-02 as a separate dimension from confidence tiers.
- Added User Feedback Queue (T08-06) to EPIC-08 for analyst-gated consultant feedback.
- Added operational risk buffer note to T02-06 (Dataset Seeding) as the highest-variance task in the roadmap.

---

## Epic Index

| ID       | Title                                                          | Tickets |
|----------|----------------------------------------------------------------|---------|
| EPIC-00  | Product Architecture, Governance & System Design               | 9       |
| EPIC-01  | Engineering Standards, Repository Bootstrap & Core Infrastructure | 16    |
| EPIC-02  | Core Data Governance & Regulatory Intelligence                 | 7       |
| EPIC-03  | Deterministic Rules Engine                                     | 6       |
| EPIC-04  | Rule Validation, Simulation & QA/QC                            | 5       |
| EPIC-05  | Lightweight GIS & Spatial Intelligence                         | 6       |
| EPIC-06  | Consultant Intake & Project Workflows                          | 4       |
| EPIC-07  | Permit Matrix & Consultant Deliverables                        | 4       |
| EPIC-08  | Regulatory Operations & Human Review                           | 6       |
| EPIC-09  | Explainable AI Assistance                                      | 4       |

---

## EPIC-00 — Product Architecture, Governance & System Design

**Objective:** Define the deterministic foundation of the platform before engineering implementation begins.

### T00-01 — Define Regulatory Rule Object Specification
Design the canonical declarative rule format governing permits, triggers, thresholds, dependencies, jurisdictions, confidence tiers, provenance, and temporal activation logic.

**Requirements:**
- Rules must remain declarative
- Rules must be explainable
- Rules must be editable without deployments
- Rules must be human-readable
- Rules must be versionable
- Rules must be testable

### T00-02 — Define Jurisdiction Ontology Model
Create the formal hierarchy and relationship structure for federal, state, county, municipality, ETJ, utility district, drainage district, river authority, and special jurisdiction logic.

**Requirements:**
- Document override precedence
- Document inheritance behavior
- Document overlap handling
- Define canonical naming standards
- Define alias management
- Define geographic normalization standards

### T00-03 — Define Temporal Versioning Model
Design the historical evaluation framework allowing projects to be evaluated against regulations active during specific time periods.

**Requirements:**
- Support effective dates
- Support superseded rules
- Support historical replay
- Support grandfathered evaluations
- Support audit reproducibility

### T00-04 — Define Permit Dependency & Sequencing Model
Create the deterministic dependency system defining prerequisite permits, sequencing recommendations, parallel workflows, agency review dependencies, and likely review bottlenecks.

### T00-05 — Define Explainability & Traceability Standards
Establish the output structure explaining why a permit triggered, which rule triggered it, applicable thresholds, jurisdiction source, source citations, confidence logic, and known unknowns.

### T00-06 — Create Benchmark Project Test Suite
Develop historical benchmark projects used for regression testing, edge-case validation, deterministic output verification, and future rules-engine QA/QC.

**Benchmark categories:**
- Simple linear projects
- Multi-county projects
- Federal nexus projects
- Conflicting jurisdictions
- Temporal versioning cases
- Known unknown scenarios

**Dependencies:**
- Downstream: `T02-06`, `T04-02`
- Note: Benchmark definitions are created here as design artifacts. They become executable only after T02-06 seeds real regulatory data, and are validated continuously via T04-02.

### T00-07 — Draft Engineering Handbook
Create the mandatory engineering handbook defining architecture standards, rules engine behavior, editing procedures, deployment safety, testing requirements, rollback procedures, and debugging workflows.

**Requirements:**
- Explain how to safely edit functions
- Explain how to safely modify permit rules
- Explain inheritance logic
- Explain how to avoid breaking deterministic outputs

### T00-08 — Create Jurisdiction Naming & Normalization Standard
Define canonical jurisdiction naming, internal IDs, aliases, temporal jurisdiction validity, and geographic traceability standards.

### T00-09 — Create Regulatory Analyst SOP Manual
Develop the operational SOP for source collection, normalization, rule drafting, validation, benchmark testing, peer review, publication approval, and emergency rule updates.

---

## EPIC-01 — Engineering Standards, Repository Bootstrap & Core Infrastructure

**Objective:** Build the maintainable engineering foundation enforcing long-term scalability and readability.

### T01-01 — Configure Repository & CI/CD Environment
Establish repository structure, deployment pipelines, staging environments, branch standards, and code review standards.

### T01-02 — Implement Engineering Constraints & Linters
Enforce maximum 60-line functions, readability standards, explicit logic, low-complexity functions, and maintainability-first architecture.

**Requirements:**
- Functions must remain under 60 lines
- Functions must remain simple
- Functions must avoid unnecessary abstraction
- Functions must be easy for engineers to understand quickly

### T01-03 — Establish Declarative Rules Repository
Build the version-controlled rule storage system ensuring rules remain editable without deployments, rule history is preserved, and auditability is maintained.

### T01-04 — Implement Audit Logging Infrastructure
Create immutable logging for rule changes, reviewer actions, permit output modifications, publication history, and system evaluations.

### T01-05 — Initialize Monorepo Structure
Create repository structure for backend services, rules engine, GIS services, frontend web app, analyst portal, shared schemas, infrastructure, documentation, benchmark projects, and regulatory operations tooling.

**Suggested structure:**
- `apps/` → `web`, `analyst-portal`
- `services/` → `rules-engine`, `gis-engine`, `ai-assistant`, `regulatory-monitor`
- `packages/` → `shared-schemas`, `jurisdiction-models`, `rule-definitions`, `benchmark-projects`
- `rules/` → `draft`, `published`, `effective`, `archived`
- Root: `infrastructure/`, `docs/`, `scripts/`, `tests/`

### T01-06 — Establish Branching Strategy
Implement main, develop, feature branches, release branches, and hotfix workflow.

**Requirements:**
- Protect main branch
- Protect production deployments
- Protect published rules
- Protect rule publication workflows

### T01-07 — Configure GitHub Actions CI Pipelines
Implement automated linting, testing, function-length checks, schema validation, rule validation, regression testing, and deployment checks.

### T01-08 — Build Environment Configuration System
Create local development config, staging config, production config, secrets handling standards, and environment variable standards.

### T01-09 — Configure Infrastructure-as-Code
Set up Terraform, Pulumi, or equivalent for database provisioning, spatial database provisioning, storage provisioning, backend service infrastructure, and CI/CD infrastructure.

### T01-10 — Initialize Documentation Structure
Create documentation directories for architecture, rules, GIS, operations, analyst SOPs, testing, and engineering handbook.

**Directories:**
- `/docs/architecture`
- `/docs/rules`
- `/docs/gis`
- `/docs/operations`
- `/docs/analyst-sops`
- `/docs/testing`
- `/docs/engineering-handbook`

### T01-11 — Create Shared Schema Packages
Build shared models for rule objects, jurisdictions, GIS overlays, permit outputs, audit logs, benchmark projects, confidence tiers, and source provenance.

### T01-12 — Configure Developer Experience Tooling
Implement pre-commit hooks, formatter standards, schema validators, local test runners, Docker development containers, and developer setup scripts.

### T01-13 — Create GitHub Project Management Templates
Create issue templates, bug report templates, feature request templates, rule update templates, pull request template, CODEOWNERS, and contribution standards.

### T01-14 — Implement Auth, RBAC & Tenant Isolation
Build authentication, role-based access control, and tenant isolation to support multi-user consultant workflows and enterprise access. Define roles for consultants, regulatory analysts, and platform admins.

**Requirements:**
- Support individual consultant accounts
- Support enterprise team accounts
- Define role hierarchy: platform admin, regulatory analyst, consultant user
- Isolate project data between tenants
- Support future SSO/OAuth integration

### T01-15 — Define API Contract & Surface Design
Design the API boundary between the deterministic rules engine, GIS services, frontend applications, and export/deliverable layer. Define request/response contracts, versioning strategy, and error handling conventions.

**Requirements:**
- Formalize rules engine input/output contract
- Formalize GIS overlay query contract
- Formalize permit matrix output contract
- Define API versioning strategy
- Document error and advisory response structures

### T01-16 — PostGIS & Spatial Infrastructure Planning
Evaluate and plan spatial database infrastructure requirements early so that hosting, CI/CD, and deployment decisions account for PostGIS or equivalent spatial DB needs before EPIC-05 implementation begins.

**Requirements:**
- Document hosting requirements for spatial DB
- Ensure CI/CD pipeline supports spatial extension testing
- Confirm staging environment compatibility
- Identify managed PostGIS options vs self-hosted trade-offs

**Dependencies:**
- Upstream: `T01-01`, `T01-09`
- Downstream: `T05-01`
- Note: This is a planning and decision ticket. Implementation of the spatial DB occurs in T05-01.

---

## EPIC-02 — Core Data Governance & Regulatory Intelligence

**Objective:** Build the regulatory intelligence backbone powering deterministic evaluations, and seed the initial Texas dataset.

### T02-01 — Build Jurisdiction Hierarchy Database
Implement jurisdiction inheritance, overlap handling, alias support, canonical naming, geographic normalization, parent-child relationships, and temporal jurisdiction validity.

### T02-02 — Develop Regulatory Intelligence Schema
Build the regulatory data structure storing permit metadata, agencies, forms, submission references, thresholds, citations, timelines, reviewer data, known unknowns, and advisories.

### T02-03 — Implement Confidence Tier Framework
Build the Tier 1, Tier 2, and Tier 3 confidence classification system.

| Tier | Definition |
|------|------------|
| Tier 1 | Fully supported and verified |
| Tier 2 | Partially verified |
| Tier 3 | Informational/reference only |

### T02-04 — Implement Temporal Rule Activation Logic
Enable historical evaluations, effective-date handling, grandfathered evaluations, and archived rule replay.

### T02-05 — Build Regulatory Source Tracking System
Track source URLs, statutes, ordinances, agency references, verification timestamps, superseded rules, reviewers, and confidence tiers.

### T02-06 — Initial Dataset Seeding & Ingestion Playbook
Develop the structured workflow, templates, CSV/JSON schemas, and normalization standards required to translate initial Texas utility/transmission regulatory data into the live platform. **This must complete before rules engine testing (EPIC-03/04) can use real data.**

**Requirements:**
- Support spreadsheet normalization
- Support canonical naming enforcement
- Support alias mapping
- Support source verification
- Support structured rule conversion
- Support provenance preservation

**Dependencies:**
- Upstream: `T02-01`, `T02-02`, `T02-03`, `T02-05`
- Downstream: `T03-01`, `T04-02`
- Note: Seeding depends on the schema and governance structures from T02-01 through T02-05. Rules engine testing and benchmark regression (T04-02) depend on seeded data being available.

**Moved from:** EPIC-08 (T08-05)
**Move rationale:** Real regulatory data must be loaded before the rules engine (EPIC-03) and benchmark validation (EPIC-04) can be meaningfully tested.

> ⚠ **Operational risk:** This is the single highest-variance task in the roadmap. Translating real Texas utility/transmission regulatory knowledge into structured, normalized, citation-backed rule objects for the first time has no existing template to follow. Seeding velocity will set the pace for rules engine validation, benchmark testing, and downstream QA. **Build scheduling buffer here.**

### T02-07 — Implement Data Freshness Scoring
Build a freshness scoring system separate from confidence tiers. A rule may be high-confidence but stale. Freshness tracks time since last verification, source URL reachability, form/submission process changes, and time since the source agency last updated the underlying regulation.

**Requirements:**
- Track time since last analyst verification
- Track time since source agency last updated regulation
- Monitor source URL reachability
- Detect changed forms or submission processes
- Trigger analyst review alerts independent of confidence tier
- Display freshness score alongside confidence tier in permit outputs

---

## EPIC-03 — Deterministic Rules Engine

**Objective:** Build the explainable deterministic permit evaluation engine.

### T03-01 — Build Declarative Rules Parser
Develop the deterministic parser capable of evaluating declarative regulatory logic, threshold conditions, jurisdiction inheritance, GIS triggers, and dependencies without hardcoded permit trees.

### T03-02 — Implement Rule Evaluation Engine
Build the execution system evaluating project parameters, jurisdiction overlaps, thresholds, dependencies, and temporal rules.

### T03-03 — Implement Rule Conflict Resolution System
Create deterministic conflict handling for overlapping jurisdictions, superseding requirements, contradictory thresholds, and nested jurisdiction overrides.

### T03-04 — Build Permit Dependency Sequencer
Develop the deterministic sequencing engine recommending permit order, parallel actions, likely blockers, and agency coordination timing.

### T03-05 — Build Explainability Engine
Generate traceable explanations for every permit trigger, including why it triggered, governing thresholds, applicable jurisdictions, citations, and confidence logic.

### T03-06 — Implement Known-Unknown Detection
Build uncertainty logic identifying situations requiring consultant review, agency coordination, discretionary interpretation, or manual confirmation.

---

## EPIC-04 — Rule Validation, Simulation & QA/QC

**Objective:** Ensure deterministic outputs remain stable, explainable, and regression-safe.

### T04-01 — Build Rule Simulation Engine
Allow simulated projects to run against historical rulesets, active rulesets, and hypothetical rule changes.

### T04-02 — Implement Regression Testing Framework
Validate outputs against benchmark projects to detect unintended logic changes.

**Dependencies:**
- Upstream: `T00-06`, `T02-06`
- Note: Requires benchmark project definitions from T00-06 and seeded regulatory data from T02-06 to produce meaningful regression results.

### T04-03 — Build Edge Case Testing Framework
Create automated testing for overlapping jurisdictions, conflicting triggers, ambiguous thresholds, and incomplete project data.

### T04-04 — Implement Rule Diff & Change Analysis
Generate explainable comparisons between rule revisions, output changes, and jurisdiction impacts.

### T04-05 — Build QA/QC Analyst Dashboard
Create internal tools for reviewing rule changes, validating outputs, approving publications, and tracking unresolved uncertainties.

---

## EPIC-05 — Lightweight GIS & Spatial Intelligence

**Objective:** Add jurisdiction-aware spatial intelligence without enterprise GIS complexity.

### T05-01 — Integrate Spatial Database Infrastructure
Implement PostGIS, lightweight geospatial architecture, and overlay indexing. Follows infrastructure decisions made in T01-16.

**Dependencies:**
- Upstream: `T01-16`
- Note: Hosting and deployment decisions from T01-16 must be finalized before standing up the spatial DB.

### T05-02 — Build Shapefile & KMZ Ingestion Service
Allow footprint uploads, route parsing, geometry normalization, and geospatial validation.

### T05-03 — Implement County & Municipality Detection
Automatically detect county intersections, municipalities, ETJs, and utility districts.

### T05-04 — Implement Environmental Overlay Lookups
Build lightweight overlays for FEMA, watershed boundaries, USACE districts, and federal nexus indicators.

### T05-05 — Integrate GIS-Driven Intake Modifiers
Dynamically modify intake workflows based on detected spatial jurisdictions.

### T05-06 — Build Auto-Detection Review & Confirmation Workflow
After a user uploads a shapefile or KMZ, the system must automatically detect likely project jurisdictions and spatial overlays, then require user review before generating the permit matrix.

**Auto-detected fields:**
- state
- county/counties
- municipalities
- ETJs
- watershed boundaries
- FEMA overlap
- USACE district
- utility districts where available
- special jurisdictions where available

**Requirements:**
- Display detected results clearly
- Allow the user to confirm results
- Allow manual edits and corrections
- Preserve the original auto-detection result
- Log any user overrides
- Use confirmed values as the source of truth for the permit matrix
- Manual entry must remain available as a fallback for early-stage projects without finalized route files

---

## EPIC-06 — Consultant Intake & Project Workflows

**Objective:** Build the consultant-facing intake system and workflow orchestration.

### T06-01 — Build Consultant Frontend Shell & Navigation
Implement the primary consultant-facing web application shell including navigation, project dashboard, and layout framework. This is the container for all consultant-facing UI built in EPIC-06 and EPIC-07.

**Requirements:**
- Responsive layout for desktop and tablet
- Project list and dashboard view
- Navigation between intake, permit matrix, deliverables, and project history
- Integrate with auth and RBAC from T01-14

### T06-02 — Build Dynamic Project Intake Form
Create adaptive intake forms responding to project type, uploaded shapefile/KMZ results, confirmed jurisdictions, GIS overlaps, utility categories, and federal nexus indicators.

**Workflow priority:**
1. Shapefile/KMZ upload with auto-detection
2. User review and confirmation
3. Manual entry fallback when no route file is available

### T06-03 — Implement Texas Utility/Transmission Modifiers
Add Texas-specific utility logic including TxDOT, utility ROWs, transmission corridors, and utility district interactions.

### T06-04 — Implement Project Persistence & Revision Tracking
Allow projects to save evaluations, preserve historical snapshots, compare revisions, and maintain audit history.

---

## EPIC-07 — Permit Matrix & Consultant Deliverables

**Objective:** Deliver explainable consultant-ready outputs.

### T07-01 — Build Permit Matrix Generator
Generate structured outputs containing likely permits, agencies, forms, timelines, sequencing guidance, and confidence tiers.

### T07-02 — Implement Explainable Permit Outputs
Display trigger explanations, governing citations, source traceability, and uncertainty flags.

### T07-03 — Enforce Liability & Advisory Framework
Apply mandatory advisory language and prevent authoritative compliance wording.

### T07-04 — Build Exportable Deliverables Engine
Export Excel matrices, PDF summaries, proposal-ready tables, and audit-ready reports.

---

## EPIC-08 — Regulatory Operations & Human Review

**Objective:** Build the operational tooling required to maintain regulatory intelligence quality.

### T08-01 — Build Regulatory Analyst Portal
Create internal dashboards for rule review, jurisdiction management, reviewer assignment, and publication workflows.

### T08-02 — Build Internal Frontend Shell & Admin Navigation
Implement the internal-facing web application shell for regulatory analysts and platform admins, including navigation to analyst portal, QA dashboards, publication workflows, and rule health monitoring.

**Requirements:**
- Separate from consultant-facing frontend (T06-01)
- Role-gated access via T01-14 RBAC
- Navigation between analyst portal, QA/QC dashboard (T04-05), publication workflows, and monitoring views

### T08-03 — Implement Source Expiration Monitoring
Flag stale citations, outdated forms, broken source links, and aging rules.

### T08-04 — Build Regulatory Publication Workflow
Require analyst verification, approval chains, publication logs, and rollback capability.

### T08-05 — Implement Rule Health Monitoring
Track frequently overridden rules, uncertainty-heavy outputs, user-reported conflicts, and stale jurisdictions.

### T08-06 — Build User Feedback Queue
Create a structured feedback intake system allowing consultants to report incorrect triggers, outdated forms, bad jurisdiction detections, field-observed regulatory changes, and conflicting agency interpretations. All feedback enters an analyst review queue and **must not auto-publish or bypass verification.**

**Requirements:**
- Support structured feedback categories: bad triggers, outdated forms, jurisdiction errors, field observations, agency conflicts
- Route all feedback to analyst review queue
- Must not auto-modify live rules
- Must not bypass analyst verification or publication workflow
- Track feedback resolution status and analyst response
- Link resolved feedback to rule change audit trail where applicable

---

## EPIC-09 — Explainable AI Assistance

**Objective:** Add tightly constrained AI assistance while preserving deterministic authority.

### T09-01 — Implement AI Document Extraction Pipeline
Extract project parameters from PDFs, reports, constraints documents, and site plans.

**Requirements:**
- AI outputs must remain explainable
- AI outputs must remain reviewable
- AI outputs must remain advisory

### T09-02 — Build AI Proposal Language Assistant
Generate consultant proposal support text using deterministic permit outputs as the authoritative source.

### T09-03 — Implement AI Workflow Recommendation Assistant
Assist consultants with sequencing explanations, workflow summarization, and review preparation.

**Requirements:**
- AI must not override deterministic outputs

### T09-04 — Implement AI-Assisted Regulatory Monitoring
Use AI to identify possible ordinance updates, changed forms, and modified submission processes.

**Requirements:**
- All updates require analyst verification
- All updates require approval workflows
- All updates require publication review

---

## Deferred From MVP

- Native iOS field application
- Autonomous regulatory agents
- Full OCR pipelines beyond constrained extraction
- Advanced AI chatbot systems beyond constrained assistance
- Full environmental constraints GIS
- Enterprise environmental CRM
- Advanced geospatial analytics
- Fully autonomous AI permit interpretation
- Legal-grade compliance certification
- Nationwide rollout
