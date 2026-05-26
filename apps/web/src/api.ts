// Thin typed fetch client for the iPermit API envelope (ADR-0003).
// All reasoning stays server-side; this client only carries the bearer token,
// sends JSON, and surfaces RFC-9457 problem-details as Error messages.

import type {
  Envelope,
  EvaluateRequest,
  Identity,
  PermitMatrix,
  Project,
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
