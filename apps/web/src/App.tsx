import { useEffect, useState } from 'react';
import { me } from './api';
import { EvaluationScreen } from './components/EvaluationScreen';
import { Login } from './components/Login';
import { PricingPage } from './components/PricingPage';
import type { Identity } from './types';

const TOKEN_KEY = 'ipermit.token';
type Tab = 'evaluation' | 'pricing';

export function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('evaluation');

  useEffect(() => {
    if (!token) {
      setIdentity(null);
      return;
    }
    me(token)
      .then(setIdentity)
      .catch(() => handleLogout());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function handleLogin(newToken: string) {
    localStorage.setItem(TOKEN_KEY, newToken);
    setError(null);
    setToken(newToken);
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setIdentity(null);
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
        <>
          <nav className="nav-tabs">
            <button
              className={`nav-tab${tab === 'evaluation' ? ' nav-tab--active' : ''}`}
              onClick={() => setTab('evaluation')}
              type="button"
            >
              Evaluation
            </button>
            <button
              className={`nav-tab${tab === 'pricing' ? ' nav-tab--active' : ''}`}
              onClick={() => setTab('pricing')}
              type="button"
            >
              Plans &amp; Pricing
            </button>
          </nav>
          {tab === 'evaluation' ? (
            <EvaluationScreen token={token} identity={identity} />
          ) : (
            <PricingPage token={token} />
          )}
        </>
      )}
    </main>
  );
}
