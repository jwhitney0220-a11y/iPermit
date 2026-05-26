// Pure helpers that turn the intake form state into an EvaluateRequest.

import { JURISDICTIONS, type IntakeState } from './fields';
import type { EvaluateRequest } from './types';

function numbers(state: IntakeState): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [key, raw] of Object.entries(state.numbers)) {
    if (raw.trim() !== '' && !Number.isNaN(Number(raw))) out[key] = Number(raw);
  }
  return out;
}

export function buildRequest(state: IntakeState): EvaluateRequest {
  return {
    project_type: state.projectType,
    project: { ...state.booleans, ...numbers(state) },
    derived: { ...state.derived },
    overlays: { ...state.overlays },
    jurisdictions: JURISDICTIONS.filter((j) =>
      state.jurisdictionIds.includes(j.jurisdiction_id),
    ),
  };
}
