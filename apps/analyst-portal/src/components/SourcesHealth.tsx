import { useEffect, useState } from 'react';
import { getSourcesReport } from '../api';
import type { CitationHealth, SourcesReport } from '../types';

type Filter = 'all' | 'stale' | 'missing_url';

export function SourcesHealth({ token }: { token: string }) {
  const [report, setReport] = useState<SourcesReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('all');

  useEffect(() => {
    getSourcesReport(token)
      .then(setReport)
      .catch(() => setError('Could not load sources report'));
  }, [token]);

  if (error) return <p className="error">{error}</p>;
  if (!report) return <p className="muted">Loading…</p>;

  const rows =
    filter === 'all' ? report.citations : report.citations.filter((c) => c.health === filter);
  return (
    <section className="section">
      <div className="section__header">
        <h2>Citation Health</h2>
        <span>{report.total_citations} citations</span>
      </div>
      <FilterBar filter={filter} counts={report.health_counts} onChange={setFilter} />
      <table className="qa-table">
        <thead>
          <tr>
            <th>Rule</th>
            <th>Type</th>
            <th>Reference</th>
            <th>Verified</th>
            <th>Health</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <CitationRow key={`${c.rule_id}-${c.reference}`} row={c} />
          ))}
        </tbody>
      </table>
    </section>
  );
}

function FilterBar({
  filter,
  counts,
  onChange,
}: {
  filter: Filter;
  counts: Record<string, number>;
  onChange: (f: Filter) => void;
}) {
  const opts: { key: Filter; label: string }[] = [
    { key: 'all', label: `All (${(counts.ok ?? 0) + (counts.stale ?? 0) + (counts.missing_url ?? 0)})` },
    { key: 'stale', label: `Stale (${counts.stale ?? 0})` },
    { key: 'missing_url', label: `Missing URL (${counts.missing_url ?? 0})` },
  ];
  return (
    <div className="filter-bar">
      {opts.map((o) => (
        <button
          key={o.key}
          className={`pill${filter === o.key ? ' pill--active' : ''}`}
          onClick={() => onChange(o.key)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function CitationRow({ row }: { row: CitationHealth }) {
  return (
    <tr>
      <td>{row.rule_id}@{row.rule_version}</td>
      <td>{row.citation_type}</td>
      <td>
        {row.url ? (
          <a href={row.url} target="_blank" rel="noreferrer">
            {row.reference}
          </a>
        ) : (
          row.reference
        )}
      </td>
      <td>{row.rule_last_verified ?? '—'}</td>
      <td>
        <span className={`health health--${row.health}`}>{row.health}</span>
      </td>
    </tr>
  );
}
