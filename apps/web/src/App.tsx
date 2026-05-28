import { useEffect, useState } from 'react';
import { me } from './api';
import { Dashboard } from './components/Dashboard';
import { EvaluationScreen } from './components/EvaluationScreen';
import { Login } from './components/Login';
import { PricingPage } from './components/PricingPage';
import { Team } from './components/Team';
import type { Identity } from './types';

const TOKEN_KEY = 'ipermit.token';
type Tab = 'dashboard' | 'evaluation' | 'team' | 'pricing';
const TABS: { key: Tab; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'evaluation', label: 'Evaluation' },
  { key: 'team', label: 'Team' },
  { key: 'pricing', label: 'Plans & Pricing' },
];

export function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('dashboard');

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setIdentity(null);
  }

  useEffect(() => {
    if (!token) {
      setIdentity(null);
      return;
    }
    me(token)
      .then(setIdentity)
      .catch(() => handleLogout());
  }, [token]);

  function handleLogin(newToken: string) {
    localStorage.setItem(TOKEN_KEY, newToken);
    setError(null);
    setToken(newToken);
  }

  return (
    <main className="app">
      <header className="app__header">
        <h1>iPermit</h1>
        {identity && (
          <div className="app__user">
            <span>{identity.email}</span>
            <button onClick={handleLogout}>Sign out</button>
          </div>
        )}
      </header>
      {error && <p className="error">{error}</p>}
      {!token || !identity ? (
        <Login onLogin={handleLogin} />
      ) : (
        <AuthenticatedApp
          identity={identity}
          tab={tab}
          token={token}
          onTabChange={setTab}
        />
      )}
    </main>
  );
}

function AuthenticatedApp({
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
  return (
    <>
      <nav className="nav-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`nav-tab${tab === t.key ? ' nav-tab--active' : ''}`}
            onClick={() => onTabChange(t.key)}
            type="button"
          >
            {t.label}
          </button>
        ))}
      </nav>
      {tab === 'dashboard' && <Dashboard token={token} email={identity.email} />}
      {tab === 'evaluation' && <EvaluationScreen token={token} identity={identity} />}
      {tab === 'team' && <Team token={token} />}
      {tab === 'pricing' && <PricingPage token={token} />}
    </>
  );
}
