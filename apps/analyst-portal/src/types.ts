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

export interface QATierCounts {
  tier_1: number;
  tier_2: number;
  tier_3: number;
  unassigned: number;
}

export interface PublicationGate {
  rule_id: string;
  provenance_present: boolean;
  reviewer_present: boolean;
  confidence_tier_assigned: boolean;
  advisory_language_present: boolean;
  all_pass: boolean;
}

export interface QASummary {
  tier_counts: QATierCounts;
  pending_review_rule_ids: string[];
  publication_gate_count: number;
  failing_publication_gates: PublicationGate[];
  unresolved_unknown_count: number;
}
