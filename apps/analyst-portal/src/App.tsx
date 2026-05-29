import { useEffect, useState } from 'react';
import { me } from './api';
import { AuditLog } from './components/AuditLog';
import { FeedbackQueue } from './components/FeedbackQueue';
import { Login } from './components/Login';
import { Publications } from './components/Publications';
import type { Identity } from './types';

const TOKEN_KEY = 'ipermit.analyst.token';
type Tab = 'feedback' | 'publications' | 'audit';

export function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('feedback');

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setIdentity(null);
    setToken(null);
  }

  useEffect(() => {
    if (!token) return setIdentity(null);
    me(token).then(setIdentity).catch(() => logout());
  }, [token]);

  function handleLogin(newToken: string) {
    localStorage.setItem(TOKEN_KEY, newToken);
    setError(null);
    setToken(newToken);
  }

  return (
    <main className="portal">
      <Header identity={identity} onLogout={logout} />
      {error && <p className="error">{error}</p>}
      {!token || !identity ? (
        <Login onLogin={handleLogin} />
      ) : (
        <PortalBody identity={identity} tab={tab} token={token} onTabChange={setTab} />
      )}
    </main>
  );
}

function Header({
  identity,
  onLogout,
}: {
  identity: Identity | null;
  onLogout: () => void;
}) {
  return (
    <header className="portal__header">
      <div>
        <h1>iPermit Analyst Portal</h1>
        <p>Feedback triage and audit review</p>
      </div>
      {identity && <button onClick={onLogout}>Sign out</button>}
    </header>
  );
}

function PortalBody({
  identity,
  tab,
  token,
  onTabChange,
}: {
  identity: Identity;
  tab: Tab;
  token: string;
  onTabChange: (tab: Tab) => void;
}) {
  if (!isInternal(identity)) return <AccessNotice identity={identity} />;
  return (
    <>
      <nav className="tabs">
        <button className={tabClass(tab, 'feedback')} onClick={() => onTabChange('feedback')}>
          Feedback Queue
        </button>
        <button
          className={tabClass(tab, 'publications')}
          onClick={() => onTabChange('publications')}
        >
          Publications
        </button>
        {identity.platform_role === 'platform_admin' && (
          <button className={tabClass(tab, 'audit')} onClick={() => onTabChange('audit')}>
            Audit Log
          </button>
        )}
      </nav>
      {tab === 'feedback' && <FeedbackQueue token={token} />}
      {tab === 'publications' && <Publications token={token} />}
      {tab === 'audit' && identity.platform_role === 'platform_admin' && (
        <AuditLog token={token} />
      )}
    </>
  );
}

function AccessNotice({ identity }: { identity: Identity }) {
  return (
    <section className="panel">
      <h2>Access restricted</h2>
      <p>
        {identity.email} is signed in as {identity.platform_role}. This portal is
        limited to regulatory analysts and platform admins.
      </p>
    </section>
  );
}

function isInternal(identity: Identity) {
  return ['regulatory_analyst', 'platform_admin'].includes(identity.platform_role);
}

function tabClass(active: Tab, tab: Tab) {
  return `tab${active === tab ? ' tab--active' : ''}`;
}
