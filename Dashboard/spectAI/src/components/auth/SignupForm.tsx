// src/components/auth/SignupForm.tsx
import { useState, FormEvent } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import './LoginForm.css'; // shares base auth-form styles

interface Props {
  onSwitch: () => void;
}

export function SignupForm({ onSwitch }: Props) {
  const { signUp } = useAuth();
  const [username, setUsername] = useState('');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [success, setSuccess]   = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (password.length < 8) { setError('Password must be at least 8 characters'); return; }
    setLoading(true);
    setError(null);
    try {
      await signUp(email, password, username);
      setSuccess(true);
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="auth-form">
        <div className="auth-form__eyebrow">Almost there</div>
        <h1 className="auth-form__title">Check email</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: '1.6' }}>
          We sent a confirmation link to <strong style={{ color: 'var(--text-primary)' }}>{email}</strong>.
          Click it to activate your account.
        </p>
        <button className="auth-form__submit" onClick={onSwitch}>Back to sign in</button>
      </div>
    );
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="auth-form__eyebrow">New agent</div>
      <h1 className="auth-form__title">Create Account</h1>

      {error && <div className="auth-form__error">{error}</div>}

      <div className="auth-form__field">
        <label htmlFor="signup-username">Username</label>
        <input
          id="signup-username"
          type="text"
          value={username}
          onChange={e => setUsername(e.target.value)}
          required
          placeholder="your_callsign"
        />
      </div>

      <div className="auth-form__field">
        <label htmlFor="signup-email">Email</label>
        <input
          id="signup-email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
          placeholder="agent@domain.com"
        />
      </div>

      <div className="auth-form__field">
        <label htmlFor="signup-password">Password</label>
        <input
          id="signup-password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
          placeholder="min. 8 characters"
        />
      </div>

      <button className="auth-form__submit" type="submit" disabled={loading}>
        {loading ? <span className="auth-form__spinner" /> : 'Deploy'}
      </button>

      <p className="auth-form__switch">
        Already have an account?{' '}
        <button type="button" className="auth-form__link" onClick={onSwitch}>
          Sign in
        </button>
      </p>
    </form>
  );
}
