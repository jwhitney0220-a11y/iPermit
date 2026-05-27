import { useEffect, useState } from 'react';
import { ApiError, getEvaluation, listEvaluations } from '../api';
import type { Envelope, EvaluationSummary, PermitMatrix } from '../types';

export function HistoryPanel({
  token,
  projectId,
  refreshKey,
  onView,
}: {
  token: string;
  projectId: string;
  refreshKey: number;
  onView: (envelope: Envelope<PermitMatrix>) => void;
}) {
  const [rows, setRows] = useState<EvaluationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) {
      setRows([]);
      return;
    }
    listEvaluations(token, projectId)
      .then(setRows)
      .catch(() => setError('Could not load history'));
  }, [token, projectId, refreshKey]);

  async function view(evaluationId: string) {
    try {
      onView(await getEvaluation(token, projectId, evaluationId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load evaluation');
    }
  }

  if (!projectId) return null;
  return (
    <section className="card">
      <h2>History</h2>
      {error && <p className="error">{error}</p>}
      {rows.length === 0 ? (
        <p className="muted">No evaluations yet.</p>
      ) : (
        <ul className="history">
          {rows.map((r) => (
            <li key={r.evaluation_id}>
              <span>{r.evaluation_date}</span>
              <span>{r.permit_count} permits</span>
              <span className="muted">{new Date(r.created_at).toLocaleString()}</span>
              <button type="button" onClick={() => view(r.evaluation_id)}>
                View
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
