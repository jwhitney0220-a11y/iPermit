import { useEffect, useState } from 'react';
import { me } from './api';
import { Login } from './components/Login';
import { EvaluationScreen } from './components/EvaluationScreen';
import type { Identity } from './types';

const TOKEN_KEY = 'ipermit.token';

export function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [error, setError] = useState<string | null>(null);

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
        <EvaluationScreen token={token} identity={identity} />
      )}
    </main>
  );
}
