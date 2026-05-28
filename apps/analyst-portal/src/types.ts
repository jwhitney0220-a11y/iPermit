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
