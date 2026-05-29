export interface Identity {
  subject: string;
  email: string;
  platform_role: string;
  tenant_ids: string[];
  tenant_id: string | null;
}

export interface FeedbackItem {
  feedback_id: string;
  tenant_id: string;
  project_id: string | null;
  evaluation_id: string | null;
  submitted_by: string;
  category: string;
  message: string;
  status: string;
  disposition_note: string | null;
  dispositioned_by: string | null;
  created_at: string;
  dispositioned_at: string | null;
}

export interface Publication {
  id: number;
  rule_id: string;
  rule_version: string;
  target_status: string;
  status: string;
  proposed_by: string;
  proposed_at: string;
  reason: string | null;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
}

export interface StaleRule {
  rule_id: string;
  rule_version: string;
  status: string;
  last_verified: string | null;
  days_since_verified: number | null;
}

export interface QaReport {
  generated_at: string;
  total_rules: number;
  by_status: Record<string, number>;
  by_tier: Record<string, number>;
  stale_rules: StaleRule[];
}

export interface CitationHealth {
  rule_id: string;
  rule_version: string;
  rule_status: string;
  citation_type: string;
  reference: string;
  url: string | null;
  rule_last_verified: string | null;
  days_since_verified: number | null;
  health: 'ok' | 'stale' | 'missing_url';
}

export interface SourcesReport {
  generated_at: string;
  total_citations: number;
  health_counts: Record<string, number>;
  citations: CitationHealth[];
}

export interface AuditRecord {
  id: number;
  occurred_at: string;
  actor: string;
  action: string;
  subject: string;
  payload: Record<string, unknown>;
  prev_hash: string | null;
  hash: string;
}
