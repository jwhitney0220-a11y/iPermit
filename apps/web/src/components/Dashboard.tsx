import { useEffect, useState } from 'react';
import { getBilling, getUsage, listProjects } from '../api';
import type { BillingStatus, Project, UsageSummary } from '../types';

export function Dashboard({ token, email }: { token: string; email: string }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listProjects(token), getBilling(token), getUsage(token)])
      .then(([p, b, u]) => {
        setProjects(p);
        setBilling(b);
        setUsage(u);
      })
      .catch(() => setError('Could not load dashboard'));
  }, [token]);

  return (
    <div className="dashboard">
      {error && <p className="error">{error}</p>}
      <div className="cards">
        <section className="card stat">
          <h3>Plan</h3>
          <p className="stat__value">{billing?.plan ?? '—'}</p>
          <p className="muted">{billing?.status ?? ''}</p>
        </section>
        <section className="card stat">
          <h3>Projects</h3>
          <p className="stat__value">{projects.length}</p>
          <p className="muted">{email}</p>
        </section>
        <section className="card stat">
          <h3>Usage this period</h3>
          <p className="stat__value">{usage?.metrics?.evaluation ?? 0}</p>
          <p className="muted">
            evaluations · {usage?.metrics?.export ?? 0} exports
          </p>
        </section>
      </div>
      <section className="card">
        <h2>Projects</h2>
        {projects.length === 0 ? (
          <p className="muted">No projects yet — start one on the Evaluation tab.</p>
        ) : (
          <ul className="project-list">
            {projects.map((p) => (
              <li key={p.project_id}>
                <span>{p.name}</span>
                <code className="muted">{p.project_id.slice(0, 8)}</code>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
