// src/components/auth/LoginForm.tsx
import { useState, FormEvent } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import './LoginForm.css';

interface Props {
  onSwitch: () => void;
}

export function LoginForm({ onSwitch }: Props) {
  const { signIn } = useAuth();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="auth-form__eyebrow">Welcome back</div>
      <h1 className="auth-form__title">Sign In</h1>

      {error && <div className="auth-form__error">{error}</div>}

      <div className="auth-form__field">
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
          placeholder="agent@domain.com"
        />
      </div>

      <div className="auth-form__field">
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
          placeholder="••••••••"
        />
      </div>

      <button className="auth-form__submit" type="submit" disabled={loading}>
        {loading ? <span className="auth-form__spinner" /> : 'Enter'}
      </button>

      <p className="auth-form__switch">
        No account?{' '}
        <button type="button" className="auth-form__link" onClick={onSwitch}>
          Create one
        </button>
      </p>
    </form>
  );
}
