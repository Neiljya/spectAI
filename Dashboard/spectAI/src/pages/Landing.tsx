// src/pages/Landing.tsx
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Banner } from '@/components/ui/Banner'; 
import './Landing.css';

const FEATURES = [
  {
    id: '01',
    title: 'Live Analysis',
    desc: 'Gemini Flash reads your screen in real-time. Rotations, utility, positioning — called before you need to think.',
  },
  {
    id: '02',
    title: 'Voice Coaching',
    desc: 'Ask mid-round. FetchAI dispatches your query instantly to the model, keeping you in the game.',
  },
  {
    id: '03',
    title: 'Post-Match Intel',
    desc: 'Every match uploaded, indexed, analyzed. Patterns surface across dozens of games, not just one.',
  },
  {
    id: '04',
    title: 'Training Plans',
    desc: 'Weaknesses scored, drills assigned. A plan built from your actual data, not generic advice.',
  },
];

const STATS = [
  { value: '<80ms', label: 'Analysis latency' },
  { value: '24+',  label: 'Tracked metrics' },
  { value: '5',    label: 'Skill dimensions' },
];

export function LandingPage() {
  const navigate = useNavigate();
  const [showPromoBanner, setShowPromoBanner] = useState(true); 

  return (
    <div className="landing">
      {/* ── Global Announcement Banner ── */}
      {showPromoBanner && (
        <div style={{ position: 'relative', zIndex: 50, padding: '16px 24px 0' }}>
          <Banner type="info" onDismiss={() => setShowPromoBanner(false)}>
            🚀 <strong>SpectAI Open Beta is live!</strong> Sign up today and get your first month of Voice Coaching free.
          </Banner>
        </div>
      )}

      {/* ── Hero ── */}
      <section 
        className="landing__hero"
        style={{
          // INLINE BACKGROUND IMAGE APPLIED HERE
          backgroundImage: `linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.9)), url('https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=2000&q=80')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat'
        }}
      >
        <nav className="landing__nav">
          <div className="landing__logo">
            SPECT<span>AI</span>
          </div>
          <button className="landing__nav-cta" onClick={() => navigate('/auth')}>
            Sign in
          </button>
        </nav>

        <div className="landing__hero-body">
          <div className="landing__eyebrow anim-up">
            <span className="landing__dot" />
            AI-powered Valorant coaching
          </div>

          <h1 className="landing__headline anim-up-1">
            Stop guessing.<br />
            <span className="landing__headline-accent">Start winning.</span>
          </h1>

          <p className="landing__subhead anim-up-2">
            Real-time comms. Live game analysis. Post-match breakdowns.<br />
            SpectAI is the analyst in your ear that never tilts.
          </p>

          <div className="landing__ctas anim-up-3">
            <button className="landing__btn-primary" onClick={() => navigate('/auth')}>
              Get started free
            </button>
            <button className="landing__btn-ghost" onClick={() => navigate('/auth')}>
              Sign in
            </button>
          </div>

          <div className="landing__stats anim-up-4">
            {STATS.map(s => (
              <div className="landing__stat" key={s.label}>
                <span className="landing__stat-value mono">{s.value}</span>
                <span className="landing__stat-label label">{s.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Decorative red corner */}
        <div className="landing__corner" />
      </section>

      {/* ── Features ── */}
      <section className="landing__features">
        <div className="landing__features-header">
          <span className="label">What it does</span>
          <h2 className="landing__features-title">Four systems. One edge.</h2>
        </div>

        <div className="landing__feature-grid">
          {FEATURES.map((f, i) => (
            <div
              className="feature-card"
              key={f.id}
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="feature-card__id mono">{f.id}</div>
              <div className="feature-card__accent" />
              <h3 className="feature-card__title">{f.title}</h3>
              <p className="feature-card__desc">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA strip ── */}
      <section className="landing__strip">
        <div className="landing__strip-inner">
          <h2 className="landing__strip-title">Ready to climb?</h2>
          <button className="landing__btn-primary" onClick={() => navigate('/auth')}>
            Create account
          </button>
        </div>
      </section>

      <footer className="landing__footer">
        <span className="mono" style={{ color: 'var(--t3)', fontSize: '11px' }}>
          SPECTAI · AI COACHING PLATFORM
        </span>
      </footer>
    </div>
  );
}