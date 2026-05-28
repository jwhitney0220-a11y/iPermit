import { useEffect, useState } from 'react';
import { getQaReport } from '../api';
import type { QaReport } from '../types';

export function QaDashboard({ token }: { token: string }) {
  const [report, setReport] = useState<QaReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getQaReport(token)
      .then(setReport)
      .catch(() => setError('Could not load QA report'));
  }, [token]);

  if (error) return <p className="error">{error}</p>;
  if (!report) return <p className="muted">Loading…</p>;

  return (
    <section className="section">
      <div className="section__header">
        <h2>Rule Health</h2>
        <span>{report.total_rules} rules</span>
      </div>
      <div className="qa-stats">
        <Stat label="By status" entries={Object.entries(report.by_status)} />
        <Stat label="By confidence tier" entries={Object.entries(report.by_tier)} />
      </div>
      <h3>Stale rules ({report.stale_rules.length})</h3>
      {report.stale_rules.length === 0 ? (
        <p className="muted">All rules verified within the freshness threshold.</p>
      ) : (
        <table className="qa-table">
          <thead>
            <tr>
              <th>Rule</th>
              <th>Status</th>
              <th>Last verified</th>
              <th>Days</th>
            </tr>
          </thead>
          <tbody>
            {report.stale_rules.map((r) => (
              <tr key={`${r.rule_id}-${r.rule_version}`}>
                <td>{r.rule_id}@{r.rule_version}</td>
                <td>{r.status}</td>
                <td>{r.last_verified ?? '—'}</td>
                <td>{r.days_since_verified ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Stat({ label, entries }: { label: string; entries: [string, number][] }) {
  return (
    <div className="qa-stat">
      <h4>{label}</h4>
      <ul>
        {entries.map(([k, v]) => (
          <li key={k}>
            <span>{k}</span>
            <strong>{v}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}
