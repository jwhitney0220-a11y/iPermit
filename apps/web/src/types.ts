// Types mirroring the API contract (ADR-0003 envelope + permit-matrix.schema.json).
// Hand-written for the thin client: the API/OpenAPI is the source of truth, the
// permit-matrix is registered for schema validation but not codegen'd (ADR-0006).

export interface Advisory {
  text: string;
  origin: 'rule' | 'engine' | 'platform';
  category: string;
}

export interface Confidence {
  tier: 1 | 2 | 3;
  tier_rationale: string;
  freshness?: Record<string, unknown>;
}

export interface Citation {
  citation_type?: string;
  reference: string;
  url?: string;
}

export interface KnownUnknown {
  text: string;
  origin: string;
}

export interface Permit {
  rule_id: string;
  permit_name: string;
  agency: string;
  jurisdiction_level: string;
  confidence: Confidence;
  citations: Citation[];
  advisories: Advisory[];
  known_unknowns: KnownUnknown[];
  sequencing: { stage_index: number; on_critical_path: boolean };
  explanation_ref: Record<string, string>;
}

export interface PermitMatrix {
  schema_version: string;
  evaluation_id: string;
  project_id: string;
  evaluation_date: string;
  ruleset_version: { content_hash: string };
  inputs_hash: string;
  permits: Permit[];
  sequencing: {
    stages: { stage_index: number; permits: string[] }[];
    critical_path: string[];
    critical_path_total_days: number;
  };
}

export interface Meta {
  ruleset_version: { content_hash: string };
  evaluation_date: string;
  evaluation_mode: string;
  evaluation_id: string | null;
  schema_version: string;
}

export interface Envelope<T> {
  data: T;
  meta: Meta;
  advisories: Advisory[];
  warnings: Advisory[];
}

export interface Identity {
  subject: string;
  email: string;
  platform_role: string;
  tenant_ids: string[];
  tenant_id: string | null;
}

export interface Project {
  project_id: string;
  tenant_id: string;
  name: string;
  created_by: string;
}

export interface EvaluationSummary {
  evaluation_id: string;
  evaluation_date: string;
  inputs_hash: string;
  ruleset_content_hash: string;
  permit_count: number;
  created_at: string;
}

export interface JurisdictionEntry {
  jurisdiction_id: string;
  jurisdiction_level: string;
  canonical_name: string;
}

export interface EvaluateRequest {
  project_type: string;
  project: Record<string, unknown>;
  derived: Record<string, unknown>;
  jurisdictions: JurisdictionEntry[];
  overlays: Record<string, unknown>;
  evaluation_date?: string | null;
}

export interface PlanEntry {
  plan: string;
  display_name: string;
  description: string;
  price_monthly_usd: string | null;
  features: string[];
  premium: boolean;
}

export interface PlansResponse {
  plans: PlanEntry[];
}

export interface BillingStatus {
  tenant_id: string;
  plan: string;
  status: string;
  current_period_end: string | null;
}

export interface UsageSummary {
  tenant_id: string;
  period_start: string;
  period_end: string;
  metrics: Record<string, number>;
}

export interface TeamMember {
  user_id: string;
  email: string;
  is_team_admin: boolean;
  created_at: string;
}
