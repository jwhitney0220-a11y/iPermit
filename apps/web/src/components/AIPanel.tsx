// Constrained AI advisory surface for the consultant app (SAAS-08).
//
// Two on-demand calls a consultant can make from the evaluation flow:
//   - Narrative — renders the latest matrix as a paste-ready advisory paragraph.
//   - Intake suggestion — converts a project description into advisory fields.
// Both surfaces force the AI advisory back into the UI verbatim so the
// consultant never sees the AI output without the disclaimer.

import { useState } from 'react';
import { ApiError, requestIntakeSuggestion, requestNarrative } from '../api';
import type { Advisory, IntakeSuggestion, NarrativeData } from '../types';

const AI_DISABLED_MESSAGE = 'AI assistance is disabled in this environment.';

export function MatrixNarrativeButton({
  token,
  projectId,
}: {
  token: string;
  projectId: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<NarrativeData | null>(null);
  const [advisories, setAdvisories] = useState<Advisory[]>([]);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const envelope = await requestNarrative(token, projectId);
      setData(envelope.data);
      setAdvisories(envelope.advisories);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Narrative request failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ai-panel">
      <header className="ai-panel__header">
        <h3>AI advisory narrative</h3>
        <button onClick={run} disabled={busy} type="button">
          {busy ? 'Generating…' : 'Generate narrative'}
        </button>
      </header>
      {error && <p className="error">{error}</p>}
      {data && (
        <article className="ai-panel__body">
          <p>{data.narrative}</p>
          <p className="muted">Model: {data.model}</p>
        </article>
      )}
      {advisories.length > 0 && (
        <ul className="ai-panel__advisories">
          {advisories.map((a, i) => (
            <li key={i}>
              <strong>{a.origin}:</strong> {a.text}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function IntakeAssistPanel({ token }: { token: string }) {
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<IntakeSuggestion | null>(null);
  const [advisories, setAdvisories] = useState<Advisory[]>([]);

  async function run() {
    if (!description.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const envelope = await requestIntakeSuggestion(token, description.trim());
      setData(envelope.data);
      setAdvisories(envelope.advisories);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'AI suggest failed';
      setError(message.includes('disabled') ? AI_DISABLED_MESSAGE : message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ai-panel">
      <header className="ai-panel__header">
        <h3>AI intake suggestion</h3>
        <button onClick={run} disabled={busy || !description.trim()} type="button">
          {busy ? 'Thinking…' : 'Suggest'}
        </button>
      </header>
      <textarea
        rows={4}
        placeholder="Describe the project — e.g. 60-acre subdivision in Travis County with two stream crossings"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      {error && <p className="error">{error}</p>}
      {data && <SuggestionTable suggestion={data} />}
      {advisories.length > 0 && (
        <ul className="ai-panel__advisories">
          {advisories.map((a, i) => (
            <li key={i}>
              <strong>{a.origin}:</strong> {a.text}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SuggestionTable({ suggestion }: { suggestion: IntakeSuggestion }) {
  const rows: [string, string][] = [
    ['Project type', suggestion.project_type ?? '—'],
    ['Linear', formatBool(suggestion.linear)],
    ['Estimated acres', suggestion.estimated_acres?.toString() ?? '—'],
    ['County hint', suggestion.county_hint ?? '—'],
    ['Stream crossings', formatBool(suggestion.stream_crossings)],
    ['Wetlands present', formatBool(suggestion.wetlands_present)],
    ['Federal nexus', formatBool(suggestion.federal_nexus)],
    ['ROW type', suggestion.row_type ?? '—'],
  ];
  return (
    <div className="ai-panel__suggestion">
      <table>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <th scope="row">{k}</th>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {suggestion.advisory_notes.length > 0 && (
        <ul className="ai-panel__notes">
          {suggestion.advisory_notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      <p className="muted">Model: {suggestion.model}</p>
    </div>
  );
}

function formatBool(value: boolean | null): string {
  if (value === null) return '—';
  return value ? 'yes' : 'no';
}
