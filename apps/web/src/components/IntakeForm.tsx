import { useState } from 'react';
import {
  DERIVED_BOOLEANS,
  JURISDICTIONS,
  OVERLAY_BOOLEANS,
  PROJECT_BOOLEANS,
  PROJECT_NUMBERS,
  PROJECT_TYPES,
  emptyIntake,
  federalNexusPrefill,
  type IntakeState,
} from '../fields';
import { CheckboxList, NumberList } from './FormControls';

export function IntakeForm({
  busy,
  onEvaluate,
}: {
  busy: boolean;
  onEvaluate: (state: IntakeState) => void;
}) {
  const [state, setState] = useState<IntakeState>(emptyIntake);

  const setBool = (group: keyof IntakeState) => (name: string, checked: boolean) =>
    setState((s) => ({ ...s, [group]: { ...(s[group] as object), [name]: checked } }));
  const setNum = (name: string, value: string) =>
    setState((s) => ({ ...s, numbers: { ...s.numbers, [name]: value } }));
  const toggleJurisdiction = (id: string) =>
    setState((s) => ({
      ...s,
      jurisdictionIds: s.jurisdictionIds.includes(id)
        ? s.jurisdictionIds.filter((j) => j !== id)
        : [...s.jurisdictionIds, id],
    }));

  return (
    <form
      className="intake"
      onSubmit={(e) => {
        e.preventDefault();
        onEvaluate(state);
      }}
    >
      <div className="intake__bar">
        <label>
          Project type
          <select
            value={state.projectType}
            onChange={(e) => setState((s) => ({ ...s, projectType: e.target.value }))}
          >
            {PROJECT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => setState(federalNexusPrefill())}>
          Prefill federal-nexus example
        </button>
      </div>
      <fieldset>
        <legend>Applicable jurisdictions (manual entry)</legend>
        {JURISDICTIONS.map((j) => (
          <label key={j.jurisdiction_id} className="checkbox">
            <input
              type="checkbox"
              checked={state.jurisdictionIds.includes(j.jurisdiction_id)}
              onChange={() => toggleJurisdiction(j.jurisdiction_id)}
            />
            {j.canonical_name} ({j.jurisdiction_level})
          </label>
        ))}
      </fieldset>
      <CheckboxList
        title="Project attributes"
        names={PROJECT_BOOLEANS}
        values={state.booleans}
        onChange={setBool('booleans')}
      />
      <NumberList
        title="Project measures"
        names={PROJECT_NUMBERS}
        values={state.numbers}
        onChange={setNum}
      />
      <CheckboxList
        title="Environmental overlays (geometry)"
        names={OVERLAY_BOOLEANS}
        values={state.overlays}
        onChange={setBool('overlays')}
      />
      <CheckboxList
        title="Derived findings"
        names={DERIVED_BOOLEANS}
        values={state.derived}
        onChange={setBool('derived')}
      />
      <button disabled={busy} type="submit">
        {busy ? 'Evaluating…' : 'Evaluate permits'}
      </button>
    </form>
  );
}
