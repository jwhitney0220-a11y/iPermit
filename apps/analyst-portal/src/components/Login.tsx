import { useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, login } from '../api';

export function Login({ onLogin }: { onLogin: (token: string) => void }) {
  const [email, setEmail] = useState('analyst@example.com');
  const [password, setPassword] = useState('password');
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      onLogin(await login(email, password));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed');
    }
  }

  return (
    <form className="login panel" onSubmit={submit}>
      <h2>Internal sign in</h2>
      {error && <p className="error">{error}</p>}
      <label>
        Email
        <input value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label>
        Password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      <button type="submit">Sign in</button>
    </form>
  );
}
