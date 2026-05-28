import { useEffect, useState } from 'react';
import { listAudit } from '../api';
import type { AuditRecord } from '../types';

export function AuditLog({ token }: { token: string }) {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAudit(token)
      .then(setRecords)
      .catch(() => setError('Could not load audit records'));
  }, [token]);

  return (
    <section className="section">
      <div className="section__header">
        <h2>Audit Log</h2>
        <span>{records.length} records</span>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="audit-table">
        {records.map((record) => (
          <AuditRow key={record.id} record={record} />
        ))}
      </div>
    </section>
  );
}

function AuditRow({ record }: { record: AuditRecord }) {
  return (
    <article className="audit-row">
      <span>#{record.id}</span>
      <span>{record.action}</span>
      <span>{record.actor}</span>
      <span>{record.subject}</span>
      <code>{record.hash.slice(0, 12)}</code>
    </article>
  );
}
