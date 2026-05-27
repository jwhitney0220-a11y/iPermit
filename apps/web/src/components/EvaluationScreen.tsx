import { useEffect, useState } from 'react';
import { ApiError, createProject, evaluate, listProjects } from '../api';
import { buildRequest } from '../intake';
import type { IntakeState } from '../fields';
import type { Envelope, Identity, PermitMatrix, Project } from '../types';
import { HistoryPanel } from './HistoryPanel';
import { IntakeForm } from './IntakeForm';
import { PermitMatrixView } from './PermitMatrix';

export function EvaluationScreen({ token, identity }: { token: string; identity: Identity }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>('');
  const [newName, setNewName] = useState('');
  const [result, setResult] = useState<Envelope<PermitMatrix> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [historyKey, setHistoryKey] = useState(0);

  useEffect(() => {
    listProjects(token).then(setProjects).catch(() => setError('Could not load projects'));
  }, [token]);

  async function addProject() {
    if (!newName.trim()) return;
    try {
      const project = await createProject(token, newName.trim());
      setProjects((p) => [...p, project]);
      setProjectId(project.project_id);
      setNewName('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create project');
    }
  }

  async function runEvaluation(state: IntakeState) {
    if (!projectId) {
      setError('Select or create a project first');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setResult(await evaluate(token, projectId, buildRequest(state)));
      setHistoryKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Evaluation failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="evaluation">
      <section className="card">
        <h2>Project</h2>
        <p className="muted">Tenant {identity.tenant_id ?? '(none)'}</p>
        <div className="project-picker">
          <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            <option value="">— select a project —</option>
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.name}
              </option>
            ))}
          </select>
          <input
            placeholder="New project name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <button onClick={addProject} type="button">
            Create
          </button>
        </div>
      </section>
      <section className="card">
        <h2>Intake</h2>
        <IntakeForm busy={busy} onEvaluate={runEvaluation} />
      </section>
      <HistoryPanel
        token={token}
        projectId={projectId}
        refreshKey={historyKey}
        onView={setResult}
      />
      {error && <p className="error">{error}</p>}
      {result && <PermitMatrixView envelope={result} token={token} />}
    </div>
  );
}
