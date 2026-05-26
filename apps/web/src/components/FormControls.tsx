// Small reusable form controls so each render function stays well under 60 lines.

function label(name: string): string {
  return name.replace(/_/g, ' ');
}

export function CheckboxList({
  title,
  names,
  values,
  onChange,
}: {
  title: string;
  names: string[];
  values: Record<string, boolean>;
  onChange: (name: string, checked: boolean) => void;
}) {
  return (
    <fieldset>
      <legend>{title}</legend>
      {names.map((name) => (
        <label key={name} className="checkbox">
          <input
            type="checkbox"
            checked={Boolean(values[name])}
            onChange={(e) => onChange(name, e.target.checked)}
          />
          {label(name)}
        </label>
      ))}
    </fieldset>
  );
}

export function NumberList({
  title,
  names,
  values,
  onChange,
}: {
  title: string;
  names: string[];
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
}) {
  return (
    <fieldset>
      <legend>{title}</legend>
      {names.map((name) => (
        <label key={name}>
          {label(name)}
          <input
            type="number"
            value={values[name] ?? ''}
            onChange={(e) => onChange(name, e.target.value)}
          />
        </label>
      ))}
    </fieldset>
  );
}
