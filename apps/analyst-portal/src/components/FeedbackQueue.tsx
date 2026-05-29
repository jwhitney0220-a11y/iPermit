import { useEffect, useState } from 'react';
import { ApiError, dispositionFeedback, listFeedbackQueue } from '../api';
import type { FeedbackItem } from '../types';

export function FeedbackQueue({ token }: { token: string }) {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  function refresh() {
    listFeedbackQueue(token)
      .then(setItems)
      .catch(() => setError('Could not load feedback queue'));
  }

  useEffect(refresh, [token]);

  async function disposition(id: string, decision: 'confirmed' | 'rejected') {
    setBusy(id);
    setError(null);
    try {
      await dispositionFeedback(token, id, decision, notes[id] ?? '');
      setNotes((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Disposition failed');
    } finally {
      setBusy(null);
    }
  }

  function setNote(id: string, value: string) {
    setNotes((prev) => ({ ...prev, [id]: value }));
  }

  return (
    <section className="section">
      <SectionHeader title="Open Feedback" count={items.length} />
      {error && <p className="error">{error}</p>}
      {items.length === 0 && <p className="muted">No open feedback items.</p>}
      <div className="queue">
        {items.map((item) => (
          <FeedbackRow
            key={item.feedback_id}
            busy={busy === item.feedback_id}
            item={item}
            note={notes[item.feedback_id] ?? ''}
            onNoteChange={(v) => setNote(item.feedback_id, v)}
            onDisposition={disposition}
          />
        ))}
      </div>
    </section>
  );
}

function SectionHeader({ title, count }: { title: string; count: number }) {
  return (
    <div className="section__header">
      <h2>{title}</h2>
      <span>{count} open</span>
    </div>
  );
}

function FeedbackRow({
  busy,
  item,
  note,
  onNoteChange,
  onDisposition,
}: {
  busy: boolean;
  item: FeedbackItem;
  note: string;
  onNoteChange: (value: string) => void;
  onDisposition: (id: string, decision: 'confirmed' | 'rejected') => void;
}) {
  return (
    <article className="queue__item">
      <div>
        <h3>{item.category}</h3>
        <p>{item.message}</p>
        <p className="muted">
          Tenant {item.tenant_id} submitted by {item.submitted_by}
        </p>
        <textarea
          className="queue__note"
          placeholder="Disposition note (optional, recorded on the audit log)"
          value={note}
          onChange={(e) => onNoteChange(e.target.value)}
        />
      </div>
      <div className="queue__actions">
        <button
          disabled={busy}
          onClick={() => onDisposition(item.feedback_id, 'confirmed')}
        >
          Confirm
        </button>
        <button
          disabled={busy}
          onClick={() => onDisposition(item.feedback_id, 'rejected')}
        >
          Reject
        </button>
      </div>
    </article>
  );
}
