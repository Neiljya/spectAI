import { useAuth } from '../../hooks/useAuth';
import { DrillRouter } from '../training/DrillRouter';
import type { PlayerStats } from '../../types/player';
import './TrainingTab.css';

interface Props {
  stats: PlayerStats | null;
}

export function TrainingTab({ stats }: Props) {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <div className="training-tab anim-up">
      {/* ── Drill Hub ── */}
      <section className="training-section">
        <header className="training-section__header">
          <div className="header-grp">
            <span className="label-red">Tactical Training</span>
            <h2 className="training-tab__title">Drill Laboratory</h2>
          </div>
          {stats?.current_rank && (
            <div className="glass-panel-small">
              <span className="label">Current Tier</span>
              <span className="rank-text mono">{stats.current_rank}</span>
            </div>
          )}
        </header>

        {/* DrillRouter handles the list, AI generation, and 3D Engine toggle */}
        <div className="drill-container-wrapper">
          <DrillRouter userId={user.id} />
        </div>
      </section>

      {/* ── Skill Growth ── */}
      {stats && (
        <section className="training-section">
          <div className="training-targets-glass">
            <div className="targets-header">
              <span className="label">Projected Skill Growth</span>
              <p className="label-dim">Complete drills to push your performance ceiling.</p>
            </div>
            
            <div className="targets-grid">
              {[
                { label: 'Aim',        current: stats.aim_score       ?? 0, color: 'var(--red)' },
                { label: 'Game Sense', current: stats.gamesense_score ?? 0, color: 'var(--teal)' },
                { label: 'Mechanics',  current: stats.mechanics_score ?? 0, color: '#facc15' },
                { label: 'Utility',    current: stats.util_score      ?? 0, color: '#a855f7' },
                { label: 'IGL',        current: stats.igl_score       ?? 0, color: '#3b82f6' },
              ].map(t => {
                const target = Math.min(100, t.current + 10);
                return (
                  <div className="target-item-glass" key={t.label}>
                    <div className="target-info">
                      <span className="target-label mono">{t.label}</span>
                      <span className="target-val mono">
                        {t.current} <span className="arrow">→</span> {target}
                      </span>
                    </div>
                    <div className="glass-track">
                      <div className="glass-fill--bg" style={{ width: `${target}%` }} />
                      <div 
                        className="glass-fill--current" 
                        style={{ 
                          width: `${t.current}%`, 
                          background: t.color,
                          boxShadow: `0 0 15px ${t.color}60`
                        }} 
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}