import { useEffect, useState } from 'react';
import { ApiError, createProject, evaluate, listProjects } from '../api';
import type { IntakeState } from '../fields';
import { buildRequest } from '../intake';
import type { Envelope, Identity, PermitMatrix, Project } from '../types';
import { FootprintUpload } from './FootprintUpload';
import { HistoryPanel } from './HistoryPanel';
import { IntakeForm } from './IntakeForm';
import { PermitMatrixView } from './PermitMatrix';

export function EvaluationScreen({
  token,
  identity,
}: {
  token: string;
  identity: Identity;
}) {
  const state = useEvaluationState(token);

  return (
    <div className="evaluation">
      <ProjectSection
        identity={identity}
        newName={state.newName}
        projectId={state.projectId}
        projects={state.projects}
        onCreate={state.addProject}
        onNameChange={state.setNewName}
        onProjectChange={state.setProjectId}
      />
      <FootprintUpload token={token} projectId={state.projectId} />
      <section className="card">
        <h2>Intake</h2>
        <IntakeForm busy={state.busy} onEvaluate={state.runEvaluation} />
      </section>
      <EvaluationResults
        error={state.error}
        historyKey={state.historyKey}
        projectId={state.projectId}
        result={state.result}
        token={token}
        onView={state.setResult}
      />
    </div>
  );
}

function useEvaluationState(token: string) {
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

  return {
    addProject,
    busy,
    error,
    historyKey,
    newName,
    projectId,
    projects,
    result,
    runEvaluation,
    setNewName,
    setProjectId,
    setResult,
  };
}

function ProjectSection({
  identity,
  newName,
  projectId,
  projects,
  onCreate,
  onNameChange,
  onProjectChange,
}: {
  identity: Identity;
  newName: string;
  projectId: string;
  projects: Project[];
  onCreate: () => void;
  onNameChange: (name: string) => void;
  onProjectChange: (projectId: string) => void;
}) {
  return (
    <section className="card">
      <h2>Project</h2>
      <p className="muted">Tenant {identity.tenant_id ?? '(none)'}</p>
      <ProjectPicker
        newName={newName}
        projectId={projectId}
        projects={projects}
        onCreate={onCreate}
        onNameChange={onNameChange}
        onProjectChange={onProjectChange}
      />
    </section>
  );
}

function EvaluationResults({
  error,
  historyKey,
  projectId,
  result,
  token,
  onView,
}: {
  error: string | null;
  historyKey: number;
  projectId: string;
  result: Envelope<PermitMatrix> | null;
  token: string;
  onView: (result: Envelope<PermitMatrix>) => void;
}) {
  return (
    <>
      <HistoryPanel
        token={token}
        projectId={projectId}
        refreshKey={historyKey}
        onView={onView}
      />
      {error && <p className="error">{error}</p>}
      {result && <PermitMatrixView envelope={result} token={token} />}
    </>
  );
}

function ProjectPicker({
  newName,
  projectId,
  projects,
  onCreate,
  onNameChange,
  onProjectChange,
}: {
  newName: string;
  projectId: string;
  projects: Project[];
  onCreate: () => void;
  onNameChange: (name: string) => void;
  onProjectChange: (projectId: string) => void;
}) {
  return (
    <div className="project-picker">
      <select value={projectId} onChange={(e) => onProjectChange(e.target.value)}>
        <option value="">-- select a project --</option>
        {projects.map((p) => (
          <option key={p.project_id} value={p.project_id}>
            {p.name}
          </option>
        ))}
      </select>
      <input
        placeholder="New project name"
        value={newName}
        onChange={(e) => onNameChange(e.target.value)}
      />
      <button onClick={onCreate} type="button">
        Create
      </button>
    </div>
  );
}
