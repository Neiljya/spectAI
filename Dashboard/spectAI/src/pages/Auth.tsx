// src/pages/Auth.tsx
import { useState, FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import './Auth.css';

export function AuthPage() {
  const { user, loading, signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode]         = useState<'in' | 'up'>('in');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [busy, setBusy]         = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [done, setDone]         = useState(false);

  if (loading) return null;
  if (user) return <Navigate to="/dashboard" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === 'in') {
        await signIn(email, password);
        navigate('/dashboard');
      } else {
        await signUp(email, password, username);
        setDone(true);
      }
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // A dark, moody background image to fit the gaming/tech vibe
  const bgStyle = {
    backgroundImage: `linear-gradient(rgba(5, 5, 5, 0.4), rgba(5, 5, 5, 0.8)), url('https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=2000&q=80')`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
  };

  if (done) {
    return (
      <div className="auth-page" style={bgStyle}>
        <div className="auth-box glass-panel">
          <div className="auth-box__logo">SPECT<span>AI</span></div>
          <div className="auth-box__confirm">
            <div className="auth-box__confirm-icon">✓</div>
            <h2>Check your email</h2>
            <p>Confirmation link sent to <strong>{email}</strong></p>
            <button className="auth-btn" onClick={() => setDone(false)}>Back to sign in</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page" style={bgStyle}>
      <button className="auth-page__back glass-btn-small" onClick={() => navigate('/')}>
        ← Back
      </button>

      <div className="auth-box glass-panel anim-up">
        <div className="auth-box__logo" onClick={() => navigate('/')}>SPECT<span>AI</span></div>

        {/* Tabs */}
        <div className="auth-tabs">
          <button
            className={`auth-tab ${mode === 'in' ? 'auth-tab--active' : ''}`}
            onClick={() => { setMode('in'); setError(null); }}
          >
            Sign in
          </button>
          <button
            className={`auth-tab ${mode === 'up' ? 'auth-tab--active' : ''}`}
            onClick={() => { setMode('up'); setError(null); }}
          >
            Create account
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {error && <div className="auth-error glass-error">{error}</div>}

          {mode === 'up' && (
            <div className="auth-field">
              <label className="label" htmlFor="au-username">Username</label>
              <input
                className="glass-input"
                id="au-username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="your_callsign"
                required
              />
            </div>
          )}

          <div className="auth-field">
            <label className="label" htmlFor="au-email">Email</label>
            <input
              className="glass-input"
              id="au-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="agent@domain.com"
              required
            />
          </div>

          <div className="auth-field">
            <label className="label" htmlFor="au-password">Password</label>
            <input
              className="glass-input"
              id="au-password"
              type="password"
              autoComplete={mode === 'in' ? 'current-password' : 'new-password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button className="auth-btn" type="submit" disabled={busy}>
            {busy
              ? <span className="auth-spinner" />
              : mode === 'in' ? 'Log In' : 'Sign Up'
            }
          </button>
        </form>
      </div>
    </div>
  );
}