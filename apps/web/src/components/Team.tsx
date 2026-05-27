import { useEffect, useState } from 'react';
import { ApiError, addMember, listMembers, removeMember, updateMember } from '../api';
import type { TeamMember } from '../types';

export function Team({ token }: { token: string }) {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    listMembers(token)
      .then(setMembers)
      .catch(() => setError('Could not load team'));
  }

  useEffect(refresh, [token]);

  async function run(action: Promise<unknown>, fallback: string) {
    setError(null);
    try {
      await action;
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : fallback);
    }
  }

  return (
    <div className="team">
      <section className="card">
        <h2>Team</h2>
        {error && <p className="error">{error}</p>}
        <ul className="member-list">
          {members.map((m) => (
            <li key={m.user_id}>
              <span>{m.email}</span>
              {m.is_team_admin && <span className="badge">admin</span>}
              <button
                type="button"
                onClick={() => run(updateMember(token, m.user_id, !m.is_team_admin), 'Update failed')}
              >
                {m.is_team_admin ? 'Revoke admin' : 'Make admin'}
              </button>
              <button
                type="button"
                onClick={() => run(removeMember(token, m.user_id), 'Remove failed')}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <form
          className="add-member"
          onSubmit={(e) => {
            e.preventDefault();
            if (email.trim()) {
              run(addMember(token, email.trim()), 'Add failed');
              setEmail('');
            }
          }}
        >
          <input
            type="email"
            placeholder="teammate@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button type="submit">Add member</button>
        </form>
        <p className="muted">The teammate must already have an iPermit account.</p>
      </section>
    </div>
  );
}
