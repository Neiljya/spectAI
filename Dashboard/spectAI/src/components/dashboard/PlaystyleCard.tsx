// src/components/dashboard/PlaystyleCard.tsx
import type { PlayerStats } from '@/types/player';
import './PlaystyleCard.css';

interface Props {
  stats: PlayerStats;
}

const SKILLS = [
  { key: 'aim_score',       label: 'Aim' },
  { key: 'gamesense_score', label: 'Game Sense' },
  { key: 'mechanics_score', label: 'Mechanics' },
  { key: 'util_score',      label: 'Utility' },
  { key: 'igl_score',       label: 'IGL' },
] as const;

type SkillKey = typeof SKILLS[number]['key'];

const TAG_COLORS: Record<string, string> = {
  'Entry Fragger': 'red',
  'Lurker':        'red',
  'Clutch King':   'red',
  'Aggressive':    'red',
  'Support':       'teal',
  'IGL':           'teal',
  'Anchor':        'teal',
  'Flex':          'gold',
  'Space Taker':   'gold',
  'Passive':       'muted',
};

function scoreColor(score: number): string {
  if (score >= 75) return '#4ade80'; // accent-teal
  if (score >= 50) return '#facc15'; // accent-gold
  return '#ff4655'; // accent-red
}

export function PlaystyleCard({ stats }: Props) {
  return (
    <div className="playstyle-card fade-up">
      <div className="playstyle-card__header">
        <span className="playstyle-card__eyebrow">AI Profile</span>
        <h2 className="playstyle-card__title">Playstyle Analysis</h2>
      </div>

      {/* Tags */}
      <div className="playstyle-card__tags">
        {stats.playstyle_tags?.length > 0
          ? stats.playstyle_tags.map(tag => (
              <span key={tag} className={`glass-badge glass-badge--${TAG_COLORS[tag] ?? 'muted'}`}>{tag}</span>
            ))
          : <span className="glass-badge badge--dim">No tags yet — sync tracker.gg</span>
        }
      </div>

      {/* Desc */}
      {stats.playstyle_desc && (
        <p className="playstyle-card__desc">{stats.playstyle_desc}</p>
      )}

      <div className="glass-divider" />

      {/* Skill bars */}
      <div className="playstyle-card__skills">
        {SKILLS.map(({ key, label }) => {
          const score = (stats[key as SkillKey] ?? 0) as number;
          const color = scoreColor(score);
          return (
            <div className="skill-bar" key={key}>
              <div className="skill-bar__meta">
                <span className="skill-bar__label">{label}</span>
                <span className="skill-bar__score mono" style={{ color: color, textShadow: `0 0 10px ${color}80` }}>
                  {score}
                </span>
              </div>
              <div className="skill-bar__track">
                <div
                  className="skill-bar__fill"
                  style={{
                    width: `${score}%`,
                    background: color,
                    boxShadow: `0 0 12px ${color}80`
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Agent prefs */}
      {stats.agent_prefs?.length > 0 && (
        <>
          <div className="glass-divider" />
          <div className="playstyle-card__agents">
            <span className="playstyle-card__eyebrow">Top Agents</span>
            <div className="agent-prefs">
              {stats.agent_prefs.map((a, i) => (
                <div className="agent-pref glass-item" key={i}>
                  <div className="agent-pref__rank mono">#{i + 1}</div>
                  <div className="agent-pref__info">
                    <div className="agent-pref__name">{a.name}</div>
                    <div className="agent-pref__role">{a.role}</div>
                  </div>
                  <div className="agent-pref__stats">
                    <div className="agent-pref__stat-col">
                      <span className="agent-pref__stat-val mono">{a.kd.toFixed(2)}</span>
                      <span className="agent-pref__stat-lbl">KD</span>
                    </div>
                    <div className="agent-pref__stat-col">
                      <span className="agent-pref__stat-val mono">{a.win_rate.toFixed(0)}%</span>
                      <span className="agent-pref__stat-lbl">WR</span>
                    </div>
                    <div className="agent-pref__stat-col">
                      <span className="agent-pref__stat-val mono">{a.hours}h</span>
                      <span className="agent-pref__stat-lbl">PLAYED</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}