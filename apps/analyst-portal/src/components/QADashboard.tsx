import { useEffect, useState } from 'react';
import { getQASummary } from '../api';
import type { PublicationGate, QASummary } from '../types';

export function QADashboard({ token }: { token: string }) {
  const [summary, setSummary] = useState<QASummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getQASummary(token)
      .then(setSummary)
      .catch(() => setError('Could not load QA summary'));
  }, [token]);

  if (error) return <p className="error">{error}</p>;
  if (!summary) return <p className="muted">Loading QA summary...</p>;

  return (
    <section className="section">
      <div className="section__header">
        <h2>QA Summary</h2>
        <span>{summary.publication_gate_count} rules checked</span>
      </div>
      <TierGrid summary={summary} />
      <PendingRules ids={summary.pending_review_rule_ids} />
      <GateFailures gates={summary.failing_publication_gates} />
    </section>
  );
}

function TierGrid({ summary }: { summary: QASummary }) {
  const counts = summary.tier_counts;
  return (
    <div className="metric-grid">
      <Metric label="Tier 1" value={counts.tier_1} />
      <Metric label="Tier 2" value={counts.tier_2} />
      <Metric label="Tier 3" value={counts.tier_3} />
      <Metric label="Unassigned" value={counts.unassigned} />
      <Metric label="Unknowns" value={summary.unresolved_unknown_count} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function PendingRules({ ids }: { ids: string[] }) {
  return (
    <div className="subsection">
      <h3>Pending Review</h3>
      {ids.length === 0 ? <p className="muted">No pending review rules.</p> : null}
      <div className="chip-list">
        {ids.map((id) => (
          <code key={id}>{id}</code>
        ))}
      </div>
    </div>
  );
}

function GateFailures({ gates }: { gates: PublicationGate[] }) {
  return (
    <div className="subsection">
      <h3>Publication Gate Failures</h3>
      {gates.length === 0 ? <p className="muted">All checked gates pass.</p> : null}
      {gates.map((gate) => (
        <GateFailure key={gate.rule_id} gate={gate} />
      ))}
    </div>
  );
}

function GateFailure({ gate }: { gate: PublicationGate }) {
  return (
    <article className="gate-failure">
      <code>{gate.rule_id}</code>
      <span>{missingGateLabels(gate).join(', ')}</span>
    </article>
  );
}

function missingGateLabels(gate: PublicationGate) {
  return [
    !gate.provenance_present && 'provenance',
    !gate.reviewer_present && 'reviewer',
    !gate.confidence_tier_assigned && 'confidence tier',
    !gate.advisory_language_present && 'advisory',
  ].filter(Boolean);
}
