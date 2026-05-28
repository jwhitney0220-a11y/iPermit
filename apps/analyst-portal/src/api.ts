import type {
  AuditRecord,
  FeedbackItem,
  Identity,
  Publication,
  QaReport,
  SourcesReport,
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
  if (!resp.ok) throw new ApiError(resp.status, problemMessage(body, resp.statusText));
  return body as T;
}

function problemMessage(body: unknown, fallback: string) {
  if (!body || typeof body !== 'object') return fallback;
  const detail = 'detail' in body ? body.detail : undefined;
  const title = 'title' in body ? body.title : undefined;
  return String(detail || title || fallback);
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

export function listFeedbackQueue(token: string): Promise<FeedbackItem[]> {
  return request<FeedbackItem[]>('/api/v1/feedback/queue', { method: 'GET' }, token);
}

export function dispositionFeedback(
  token: string,
  feedbackId: string,
  decision: 'confirmed' | 'rejected',
  note: string,
): Promise<FeedbackItem> {
  return request<FeedbackItem>(
    `/api/v1/feedback/${feedbackId}/disposition`,
    { method: 'POST', body: JSON.stringify({ decision, note }) },
    token,
  );
}

export function listAudit(token: string): Promise<AuditRecord[]> {
  return request<AuditRecord[]>('/api/v1/audit?limit=100', { method: 'GET' }, token);
}

export function listPublications(token: string): Promise<Publication[]> {
  return request<Publication[]>('/api/v1/rules/publications', { method: 'GET' }, token);
}

export function decidePublication(
  token: string,
  id: number,
  decision: 'approve' | 'reject' | 'rollback',
  note: string,
): Promise<Publication> {
  return request<Publication>(
    `/api/v1/rules/publications/${id}/${decision}`,
    { method: 'POST', body: JSON.stringify({ note }) },
    token,
  );
}

export function getQaReport(token: string): Promise<QaReport> {
  return request<QaReport>('/api/v1/qa/report', { method: 'GET' }, token);
}

export function getSourcesReport(token: string): Promise<SourcesReport> {
  return request<SourcesReport>('/api/v1/qa/sources', { method: 'GET' }, token);
}
