import type { Advisory, Envelope, Permit, PermitMatrix as Matrix } from '../types';

function AdvisoryList({ title, items }: { title: string; items: Advisory[] }) {
  if (items.length === 0) return null;
  return (
    <div className="advisories">
      <strong>{title}</strong>
      <ul>
        {items.map((a, i) => (
          <li key={i} className={`advisory advisory--${a.origin}`}>
            {a.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

function PermitCard({ permit }: { permit: Permit }) {
  return (
    <article className="permit">
      <header>
        <span className={`tier tier--${permit.confidence.tier}`}>
          Tier {permit.confidence.tier}
        </span>
        <h3>{permit.permit_name}</h3>
      </header>
      <p className="permit__agency">
        {permit.agency} · {permit.jurisdiction_level} · stage{' '}
        {permit.sequencing.stage_index}
      </p>
      <p className="permit__rationale">{permit.confidence.tier_rationale}</p>
      {permit.citations.length > 0 && (
        <ul className="citations">
          {permit.citations.map((c, i) => (
            <li key={i}>
              {c.url ? (
                <a href={c.url} target="_blank" rel="noreferrer">
                  {c.reference}
                </a>
              ) : (
                c.reference
              )}
            </li>
          ))}
        </ul>
      )}
      <AdvisoryList title="Advisories" items={permit.advisories} />
      {permit.known_unknowns.length > 0 && (
        <ul className="known-unknowns">
          {permit.known_unknowns.map((k, i) => (
            <li key={i}>{k.text}</li>
          ))}
        </ul>
      )}
    </article>
  );
}

export function PermitMatrixView({ envelope }: { envelope: Envelope<Matrix> }) {
  const matrix = envelope.data;
  return (
    <section className="matrix">
      <div className="matrix__meta">
        <span>{matrix.permits.length} permits</span>
        <span>evaluated {matrix.evaluation_date}</span>
        <code>{matrix.ruleset_version.content_hash.slice(0, 19)}…</code>
      </div>
      <AdvisoryList title="Platform advisories" items={envelope.advisories} />
      <AdvisoryList title="Warnings" items={envelope.warnings} />
      <div className="matrix__permits">
        {matrix.permits.map((p) => (
          <PermitCard key={`${p.rule_id}:${p.permit_name}`} permit={p} />
        ))}
      </div>
    </section>
  );
}
