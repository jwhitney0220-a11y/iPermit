import { useState } from 'react';
import { ApiError, uploadFootprint } from '../api';
import type { FootprintUpload as Upload } from '../types';

export function FootprintUpload({
  token,
  projectId,
}: {
  token: string;
  projectId: string;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Upload | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await uploadFootprint(token, projectId, file));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  }

  if (!projectId) return null;
  return (
    <section className="card">
      <h2>Route file</h2>
      <p className="muted">Upload a KML, KMZ, or zipped shapefile (max 50 MB).</p>
      <form className="footprint-upload" onSubmit={submit}>
        <input
          type="file"
          accept=".kml,.kmz,.zip"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={busy || !file}>
          {busy ? 'Uploading…' : 'Upload'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <p className="muted">
          {result.geometry_type} · bbox [{result.bbox.map((n) => n.toFixed(3)).join(', ')}] ·{' '}
          {result.byte_size} bytes
        </p>
      )}
    </section>
  );
}
