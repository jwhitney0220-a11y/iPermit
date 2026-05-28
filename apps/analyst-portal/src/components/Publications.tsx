import { useEffect, useState } from 'react';
import { ApiError, decidePublication, listPublications } from '../api';
import type { Publication } from '../types';

type Decision = 'approve' | 'reject' | 'rollback';

export function Publications({ token }: { token: string }) {
  const [rows, setRows] = useState<Publication[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);

  function refresh() {
    listPublications(token)
      .then(setRows)
      .catch(() => setError('Could not load publications'));
  }
  useEffect(refresh, [token]);

  async function decide(id: number, decision: Decision) {
    setBusy(id);
    setError(null);
    try {
      await decidePublication(token, id, decision, notes[id] ?? '');
      setNotes((p) => {
        const next = { ...p };
        delete next[id];
        return next;
      });
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Decision failed');
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="section">
      <div className="section__header">
        <h2>Rule Publications</h2>
        <span>{rows.length} records</span>
      </div>
      {error && <p className="error">{error}</p>}
      {rows.length === 0 && <p className="muted">No publications yet.</p>}
      <div className="queue">
        {rows.map((r) => (
          <PublicationRow
            key={r.id}
            row={r}
            busy={busy === r.id}
            note={notes[r.id] ?? ''}
            onNoteChange={(v) => setNotes((p) => ({ ...p, [r.id]: v }))}
            onDecide={(d) => decide(r.id, d)}
          />
        ))}
      </div>
    </section>
  );
}

function PublicationRow({
  row,
  busy,
  note,
  onNoteChange,
  onDecide,
}: {
  row: Publication;
  busy: boolean;
  note: string;
  onNoteChange: (v: string) => void;
  onDecide: (d: Decision) => void;
}) {
  const proposed = row.status === 'proposed';
  const approved = row.status === 'approved';
  return (
    <article className="queue__item">
      <div>
        <h3>
          {row.rule_id}@{row.rule_version} → {row.target_status}
        </h3>
        <p className="muted">
          {row.status} · proposed by {row.proposed_by}
          {row.decided_by ? ` · decided by ${row.decided_by}` : ''}
        </p>
        {row.reason && <p>{row.reason}</p>}
        {(proposed || approved) && (
          <textarea
            className="queue__note"
            placeholder="Decision note (recorded on the audit log)"
            value={note}
            onChange={(e) => onNoteChange(e.target.value)}
          />
        )}
      </div>
      <div className="queue__actions">
        {proposed && (
          <>
            <button disabled={busy} onClick={() => onDecide('approve')}>
              Approve
            </button>
            <button disabled={busy} onClick={() => onDecide('reject')}>
              Reject
            </button>
          </>
        )}
        {approved && (
          <button disabled={busy} onClick={() => onDecide('rollback')}>
            Rollback
          </button>
        )}
      </div>
    </article>
  );
}
