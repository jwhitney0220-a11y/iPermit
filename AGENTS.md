# iPermit — AGENTS.md

## Agent Chat Conventions

Use caveman speak from the start of each session whenever responding to me (Jake)
in this chat. This applies to chat replies only — committed artifacts (code,
docs, commit messages, rule data) stay in normal prose. Drop caveman style for
security warnings, irreversible-action confirmations, and multi-step sequences
where terse phrasing could be misread, then resume.

## Session Handoff

Whenever tokens are about to run out of the five-hour session while working on
the next task, write a handoff summary JSON for the next agent at
`docs/handoff/session-handoff.json` (commit and push it). It MUST include:

- `completed`: brief summary of what was finished this session (and the
  roadmap tickets/epics it maps to).
- `in_progress`: anything started but not finished, with file paths.
- `next_pickup`: exactly where the next agent should resume — the next task and
  the first concrete step.
- `branch` and `last_commit`: so the next agent lands in the right place.
- `verification`: the commands that must stay green (lint, tests, regression).
- `loose_ends`: known follow-ups or blockers.

Keep it short and factual — it is a baton pass, not a report.

## Product Identity
iPermit is a consultant-focused permitting intelligence and workflow platform for Texas utility and transmission infrastructure projects.

The platform is NOT a legal-grade compliance certification system.

The platform provides:
- permit intelligence
- workflow guidance
- likely permit identification
- sequencing recommendations
- regulatory references
- submission resources
- consultant support tooling
- enterprise workflow assistance
- proposal and permitting planning support

The platform does NOT guarantee:
- regulatory completeness
- legal compliance
- permit approval
- agency interpretation outcomes

All outputs are advisory and require professional review.

---

# Locked Strategic Decisions

## Primary Product Scope

Primary focus:
1. Consultant support software
2. Enterprise workflow assistance
3. Proposal and permitting planning workflows

Deferred/later products:
- Full GIS constraints platform
- Legal compliance certification
- Full environmental CRM
- Advanced field collection ecosystem

---

# Geographic Scope

## MVP Geography

Texas only.

Architecture MUST support future expansion to:
- additional U.S. states
- multi-state utility corridors
- federal regional overlays

All database structures and rule systems must be state-scalable.

---

# Primary Industry Focus

Initial target sector:
- utility transmission
- utility corridor infrastructure
- roadside utility projects
- linear infrastructure

Future expandable sectors:
- oil and gas
- solar
- wind
- BESS
- telecom
- water utilities

---

# Core Product Philosophy

The product is:
- a permitting intelligence platform
- a workflow acceleration platform
- a regulatory research assistant
- a consultant decision-support system
- an enterprise workflow support system

The product is NOT:
- a substitute for legal counsel
- a guaranteed compliance engine
- an authoritative regulatory determination system
- a legal-grade compliance certification platform

---

# Liability Strategy

All outputs MUST include:
- confidence level
- last verified date
- source citation
- reviewer attribution when available
- advisory disclaimer language

The system must communicate:
- “likely required permits”
- “commonly encountered requirements”
- “recommended workflow sequencing”
- “additional review recommended” where uncertainty exists

The system MUST NOT communicate:
- “guaranteed compliance”
- “complete permit certainty”
- “final regulatory determination”
- “legal compliance certification”

---

# Permit Confidence Tiers

## Tier 1
Fully supported and verified.
Statutory and stable requirements.

## Tier 2
Supported but partially verified.
Potentially variable local implementation.

## Tier 3
Informational/reference only.
Requires consultant confirmation.

---

# Core Competitive Moats

Priority order:
1. Regulatory intelligence database
2. Workflow sequencing engine
3. Historical permitting knowledge
4. Enterprise workflow integration
5. AI assistant tooling

AI alone is NOT considered the primary moat.

---

# MVP Functional Scope

## Inputs
- project type
- county/counties
- acreage
- linear vs nonlinear
- stream crossings
- wetlands presence
- TxDOT involvement
- federal nexus
- ROW type
- shapefile/KMZ upload where available

## Outputs
- likely permits
- likely agencies
- forms
- submission links
- sequencing guidance
- confidence scoring
- exportable permit matrix
- trigger explanations
- source citations
- uncertainty flags

---

# GIS Strategy

## MVP GIS

Lightweight overlays only.

Supported:
- state detection from uploaded shapefile/KMZ
- county intersection
- municipality overlap
- ETJ overlap
- watershed lookup
- FEMA overlap
- USACE district lookup
- utility districts where available
- special jurisdictions where available

Deferred:
- full environmental constraints mapping
- advanced geospatial analytics
- enterprise GIS workflows

## GIS Intake Strategy

Preferred intake workflow:
1. User uploads shapefile or KMZ.
2. System auto-detects project jurisdictions and spatial overlays.
3. User reviews detected results.
4. User confirms or manually edits detected values.
5. Confirmed values become the source of truth for the permit matrix.

Manual entry MUST remain available as a fallback for early-stage projects without finalized route files.

All user edits to auto-detected GIS values MUST be logged.

---

# AI Strategy

AI is NOT the primary product.

AI usage must remain:
- explainable
- reviewable
- advisory

AI may assist with:
- document extraction
- permit comparisons
- workflow recommendations
- proposal drafting assistance
- regulatory monitoring flagging

AI MUST NOT:
- hallucinate permit certainty
- override deterministic rule outputs
- make authoritative legal determinations
- publish regulatory updates without human review

Deterministic rules engine remains the source of truth.

---

# Rules Engine Architecture

Rules MUST be:
- declarative
- data-driven
- version-controlled
- editable without code deployment
- human-readable
- testable
- explainable

Rules MUST NOT:
- rely on hardcoded logic trees
- require engineering deployments for minor regulatory updates
- silently delete parent jurisdiction requirements
- hide assumptions inside procedural code

Jurisdiction hierarchy:
Federal
→ State
→ County
→ Municipality
→ ETJ
→ Utility District
→ Drainage District
→ River Authority
→ Special Jurisdiction

Lower jurisdictions may:
- add requirements
- override thresholds
- append advisories

Lower jurisdictions MUST NOT silently delete parent requirements.

---

# Rule Object Specification

Rules should include:
- rule ID
- title
- permit name
- permit code where applicable
- jurisdiction level
- source agency
- confidence tier
- effective dates
- active/superseded status
- source citations
- last verified date
- reviewer
- reviewer notes
- applicable project types
- deterministic triggers
- outputs
- agencies
- forms
- submission links
- sequencing data
- explanations
- known unknowns
- advisories

Supported trigger operators:
- =
- !=
- >
- >=
- <
- <=
- contains
- intersects
- exists
- in
- not_in

Rule evaluation order:
1. jurisdiction
2. temporal validity
3. project type
4. trigger conditions
5. spatial overlays
6. dependencies

---

# Temporal Versioning

Rules MUST support:
- effective start dates
- effective end dates
- superseded status
- historical replay
- grandfathered evaluations where appropriate
- audit reproducibility

Projects must preserve the ruleset version used at the time of evaluation.

Published rules are not necessarily effective rules. The system must distinguish:
- draft: under development, not yet reviewed
- published: approved and reviewed, but may be future-dated or pending activation
- effective: currently governing active evaluations
- archived: superseded or expired, retained for historical replay

A rule may be published before its effective date. Superseded rules may remain effective for grandfathered evaluations.

---

# Data Governance

All regulatory data should include:
- source URL
- source agency
- statute/ordinance reference
- last reviewed timestamp
- reviewer
- superseded status
- confidence tier
- data freshness score
- known unknowns
- advisories

Data freshness is a separate dimension from confidence. A rule may be high-confidence (Tier 1, statutory, well-established) but stale (last verified 18+ months ago). Freshness scoring should track:
- time since last verification
- time since source agency last updated the underlying regulation
- whether the source URL is still reachable
- whether the form or submission process has changed

Freshness alerts should trigger analyst review independent of confidence tier.

---

# Jurisdiction Naming & Normalization

Every jurisdiction MUST:
- have a permanent internal ID
- use canonical naming
- support aliases
- support temporal changes
- remain geographically traceable

Jurisdiction records should include:
- jurisdiction ID
- canonical name
- aliases
- jurisdiction type
- parent jurisdiction
- geometry reference
- active dates
- FIPS where applicable

Analysts MUST:
- avoid abbreviations in canonical names
- preserve historical names
- document mergers/splits
- maintain alias history

---

# Benchmark Project Library

Benchmark projects are core production infrastructure.

Benchmark projects provide:
- regression testing
- edge-case validation
- deterministic QA
- explainability verification

Benchmark categories MUST include:
- simple linear projects
- multi-county projects
- federal nexus projects
- conflicting jurisdiction projects
- temporal testing projects
- known unknown scenarios

Each benchmark should include:
- benchmark ID
- project inputs
- expected outputs
- expected confidence
- expected explanations
- expected known unknowns
- historical rule version

Benchmark projects MUST:
- remain immutable
- be historically reproducible
- preserve old outputs
- support audit replay

---

# Human Review Workflow

Regulatory updates should follow:
1. AI-assisted identification
2. Human analyst verification
3. Approved rule publication

Human-reviewed data is prioritized over autonomous updates.

No rule may be published unless:
- provenance exists
- explainability exists
- benchmark tests pass
- reviewer approval exists
- confidence tier is assigned

---

# Regulatory Analyst SOP Requirements

The analyst workflow must include:
1. source collection
2. normalization
3. rule drafting
4. internal validation
5. benchmark testing
6. peer review
7. publication approval

Analysts are responsible for:
- accuracy
- provenance
- explainability
- conflict resolution
- update verification

Analysts are NOT responsible for:
- guaranteeing legal compliance
- replacing agency determinations
- issuing legal advice

---

# User Feedback Queue

Consultants may submit feedback including:
- incorrect or missing permit triggers
- outdated forms or submission links
- bad jurisdiction detection results
- field-observed regulatory changes
- conflicting agency interpretations

All feedback enters an analyst review queue. Feedback MUST NOT:
- auto-publish rule changes
- bypass analyst verification
- modify live rules without approval
- create crowdsourced regulatory data

Feedback is treated as signal for analyst investigation, not as authoritative input.

---

# Initial Dataset Seeding

Before MVP launch, the team must create a dataset seeding and ingestion playbook for converting Texas utility/transmission regulatory information into the live platform.

The ingestion framework must support:
- spreadsheet normalization
- CSV/JSON templates
- canonical naming enforcement
- alias mapping
- source verification
- structured rule conversion
- provenance preservation

Operational risk note: The seeding playbook itself is a deliverable, but the actual work of translating real Texas utility/transmission regulatory knowledge into structured, normalized, citation-backed rule objects — for the first time, with no existing template — is the single highest-variance task in the roadmap. Build scheduling buffer here. Seeding velocity will set the pace for rules engine validation, benchmark testing, and downstream QA.

---

# Technical Philosophy

Priority order:
1. Maintainability
2. Explainability
3. Traceability
4. Scalability
5. Automation
6. UI polish

---

# Engineering Standards

All code functions MUST remain under 60 lines.

Functions MUST:
- use the simplest coding logic possible
- avoid unnecessary abstraction, mess, and bloat
- be easy for an engineer to read quickly
- make the function’s purpose obvious
- complete one clear task whenever possible

Code should prioritize:
- readability over cleverness
- explicit logic over hidden magic
- maintainability over premature optimization

Engineers should be able to:
- understand a function quickly
- safely modify logic
- trace rule execution paths easily
- debug permit outputs without confusion

Large systems should be split into:
- small focused services
- isolated rule modules
- clean data models
- clearly named functions and files

---

# Engineering Handbook Requirement

Before launch, the team MUST produce a full Engineering Handbook.

The handbook MUST explain:
- overall system architecture
- rules engine behavior
- database structure
- jurisdiction hierarchy logic
- confidence scoring logic
- GIS overlay workflows
- AI workflow boundaries
- how to safely edit any function
- how to safely add or modify permit rules
- how to test rule changes
- how to prevent breaking core engine behavior
- required QA/QC steps before deployment
- rollback and versioning procedures

The handbook should allow a new engineer to:
- onboard quickly
- understand the engine safely
- modify logic confidently
- maintain long-term platform stability

---

# Roadmap Philosophy

The project must follow the locked roadmap order:
1. Product architecture, governance, and system design
2. Engineering standards and core infrastructure
3. Core data governance and regulatory intelligence
4. Deterministic rules engine
5. Rule validation, simulation, and QA/QC
6. Lightweight GIS and spatial intelligence
7. Consultant intake and project workflows
8. Permit matrix and consultant deliverables
9. Regulatory operations and human review
10. Explainable AI assistance

No AI workflow should override deterministic logic.
No user-facing permit matrix should omit advisory language, citations, confidence tier, or explainability.

---

# Repository Strategy

iPermit should use a monorepo structure unless a future architecture review proves otherwise.

Suggested structure:

```
/apps
  /web
  /analyst-portal

/services
  /rules-engine
  /gis-engine
  /ai-assistant
  /regulatory-monitor

/packages
  /shared-schemas
  /jurisdiction-models
  /rule-definitions
  /benchmark-projects

/rules
  /draft
  /published
  /effective
  /archived

/infrastructure
/docs
/scripts
/tests
```

The repository must support:
- deterministic rule validation
- benchmark regression testing
- analyst review workflows
- clear separation between draft, published, effective, and archived rules
- safe future expansion to additional states

---

# Explicitly Deferred From MVP

The following are explicitly deferred from MVP:
- native iOS field application
- autonomous regulatory agents
- full OCR pipelines except limited AI document extraction
- advanced AI chatbot systems beyond constrained assistance
- enterprise environmental CRM
- full GIS constraints mapping
- advanced geospatial analytics
- fully autonomous AI permit interpretation
- legal-grade compliance certification
- nationwide rollout

These may become future roadmap items after PMF validation.
