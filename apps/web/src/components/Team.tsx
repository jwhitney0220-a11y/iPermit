import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, addMember, listMembers, removeMember, updateMember } from '../api';
import type { TeamMember } from '../types';

type TeamAction = (action: Promise<unknown>, fallback: string) => void;

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
            <MemberRow key={m.user_id} member={m} token={token} onRun={run} />
          ))}
        </ul>
        <AddMemberForm
          email={email}
          token={token}
          onEmailChange={setEmail}
          onRun={run}
        />
        <p className="muted">The teammate must already have an iPermit account.</p>
      </section>
    </div>
  );
}

function MemberRow({
  member,
  token,
  onRun,
}: {
  member: TeamMember;
  token: string;
  onRun: TeamAction;
}) {
  return (
    <li>
      <span>{member.email}</span>
      {member.is_team_admin && <span className="badge">admin</span>}
      <button
        type="button"
        onClick={() =>
          onRun(updateMember(token, member.user_id, !member.is_team_admin), 'Update failed')
        }
      >
        {member.is_team_admin ? 'Revoke admin' : 'Make admin'}
      </button>
      <button
        type="button"
        onClick={() => onRun(removeMember(token, member.user_id), 'Remove failed')}
      >
        Remove
      </button>
    </li>
  );
}

function AddMemberForm({
  email,
  token,
  onEmailChange,
  onRun,
}: {
  email: string;
  token: string;
  onEmailChange: (email: string) => void;
  onRun: TeamAction;
}) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) return;
    onRun(addMember(token, email.trim()), 'Add failed');
    onEmailChange('');
  }

  return (
    <form className="add-member" onSubmit={handleSubmit}>
      <input
        type="email"
        placeholder="teammate@example.com"
        value={email}
        onChange={(e) => onEmailChange(e.target.value)}
      />
      <button type="submit">Add member</button>
    </form>
  );
}
