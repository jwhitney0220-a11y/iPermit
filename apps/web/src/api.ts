// Thin typed fetch client for the iPermit API envelope (ADR-0003).
// All reasoning stays server-side; this client only carries the bearer token,
// sends JSON, and surfaces RFC-9457 problem-details as Error messages.

import type {
  BillingStatus,
  Envelope,
  EvaluateRequest,
  EvaluationSummary,
  Identity,
  PermitMatrix,
  PlansResponse,
  Project,
  TeamMember,
  UsageSummary,
} from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit, token?: string): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(`${BASE}${path}`, { ...init, headers });
  const text = await resp.text();
  const body = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const detail = body?.detail || body?.title || resp.statusText;
    throw new ApiError(resp.status, detail);
  }
  return body as T;
}

export async function login(email: string, password: string): Promise<string> {
  const body = await request<{ access_token: string }>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  return body.access_token;
}

export function me(token: string): Promise<Identity> {
  return request<Identity>('/api/v1/auth/me', { method: 'GET' }, token);
}

export function listProjects(token: string): Promise<Project[]> {
  return request<Project[]>('/api/v1/projects', { method: 'GET' }, token);
}

export function createProject(token: string, name: string): Promise<Project> {
  return request<Project>(
    '/api/v1/projects',
    { method: 'POST', body: JSON.stringify({ name }) },
    token,
  );
}

export function evaluate(
  token: string,
  projectId: string,
  payload: EvaluateRequest,
): Promise<Envelope<PermitMatrix>> {
  return request<Envelope<PermitMatrix>>(
    `/api/v1/projects/${projectId}/evaluate`,
    { method: 'POST', body: JSON.stringify(payload) },
    token,
  );
}

export type ExportFormat = 'json' | 'xlsx' | 'pdf';

export function listEvaluations(
  token: string,
  projectId: string,
): Promise<EvaluationSummary[]> {
  return request<EvaluationSummary[]>(
    `/api/v1/projects/${projectId}/evaluations`,
    { method: 'GET' },
    token,
  );
}

export function getEvaluation(
  token: string,
  projectId: string,
  evaluationId: string,
): Promise<Envelope<PermitMatrix>> {
  return request<Envelope<PermitMatrix>>(
    `/api/v1/projects/${projectId}/evaluations/${evaluationId}`,
    { method: 'GET' },
    token,
  );
}

export async function exportMatrix(
  token: string,
  projectId: string,
  format: ExportFormat,
): Promise<{ blob: Blob; filename: string }> {
  const resp = await fetch(`${BASE}/api/v1/projects/${projectId}/matrix/export?format=${format}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new ApiError(resp.status, body || resp.statusText);
  }
  const match = /filename="([^"]+)"/.exec(resp.headers.get('Content-Disposition') ?? '');
  return { blob: await resp.blob(), filename: match?.[1] ?? `permit-matrix.${format}` };
}

/** Fetch the server-side plan catalog (public — no auth required). */
export function getPlans(): Promise<PlansResponse> {
  return request<PlansResponse>('/api/v1/billing/plans', { method: 'GET' });
}

/** Fetch the current tenant's billing status (auth required). */
export function getBilling(token: string): Promise<BillingStatus> {
  return request<BillingStatus>('/api/v1/billing', { method: 'GET' }, token);
}

/** Fetch the current tenant's usage summary for the current period (auth). */
export function getUsage(token: string): Promise<UsageSummary> {
  return request<UsageSummary>('/api/v1/usage', { method: 'GET' }, token);
}

/** List the caller tenant's team members (auth). */
export function listMembers(token: string): Promise<TeamMember[]> {
  return request<TeamMember[]>('/api/v1/team/members', { method: 'GET' }, token);
}

/** Add an existing user to the tenant by email (team admin). */
export function addMember(
  token: string,
  email: string,
  isTeamAdmin = false,
): Promise<TeamMember> {
  return request<TeamMember>(
    '/api/v1/team/members',
    { method: 'POST', body: JSON.stringify({ email, is_team_admin: isTeamAdmin }) },
    token,
  );
}

/** Toggle a member's tenant-local admin flag (team admin). */
export function updateMember(
  token: string,
  userId: string,
  isTeamAdmin: boolean,
): Promise<TeamMember> {
  return request<TeamMember>(
    `/api/v1/team/members/${userId}`,
    { method: 'PATCH', body: JSON.stringify({ is_team_admin: isTeamAdmin }) },
    token,
  );
}

/** Remove a member from the tenant (team admin). */
export function removeMember(token: string, userId: string): Promise<unknown> {
  return request<unknown>(
    `/api/v1/team/members/${userId}`,
    { method: 'DELETE' },
    token,
  );
}

/** Start a Stripe Checkout Session for the given plan; returns a redirect URL. */
export async function startCheckout(token: string, plan: string): Promise<string> {
  const body = await request<{ checkout_url: string }>(
    '/api/v1/billing/checkout',
    { method: 'POST', body: JSON.stringify({ plan }) },
    token,
  );
  return body.checkout_url;
}

