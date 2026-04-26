// src/components/dashboard/StatsPanel.tsx
import type { PlayerStats } from '@/types/player';
import './StatsPanel.css';

interface Props { stats: PlayerStats | null; }

interface StatItem {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
}

export function StatsPanel({ stats }: Props) {
  if (!stats) {
    return (
      <div className="stats-panel fade-up">
        <div className="stats-panel__empty">
          Sync your tracker.gg profile to see stats
        </div>
      </div>
    );
  }

  const items: StatItem[] = [
    { label: 'K/D Ratio',  value: stats.kd_ratio?.toFixed(2) ?? '—', accent: (stats.kd_ratio ?? 0) >= 1.2 },
    { label: 'Headshot %', value: stats.headshot_pct != null ? `${stats.headshot_pct.toFixed(1)}%` : '—' },
    { label: 'Win Rate',   value: stats.win_rate != null ? `${stats.win_rate.toFixed(1)}%` : '—', accent: (stats.win_rate ?? 0) >= 50 },
    { label: 'ACS',        value: stats.avg_score?.toFixed(0) ?? '—', sub: 'avg combat score' },
    { label: 'Dmg / Rnd',  value: stats.avg_damage?.toFixed(0) ?? '—' },
    { label: 'Avg Kills',  value: stats.avg_kills?.toFixed(1) ?? '—' },
    { label: 'Avg Deaths', value: stats.avg_deaths?.toFixed(1) ?? '—' },
    { label: 'Clutch %',   value: stats.clutch_pct != null ? `${stats.clutch_pct.toFixed(1)}%` : '—', accent: (stats.clutch_pct ?? 0) >= 30 },
    { label: 'Aces',       value: String(stats.aces ?? 0) },
  ];

  return (
    <div className="stats-panel fade-up">
      <div className="stats-panel__header">
        <span className="stats-panel__eyebrow">Lifetime</span>
        <h2 className="stats-panel__title">Performance</h2>
      </div>
      <div className="stats-panel__grid">
        {items.map(item => (
          <div className="stat-tile" key={item.label}>
            <div className={`stat-tile__value mono ${item.accent ? 'stat-tile__value--accent' : ''}`}>
              {item.value}
            </div>
            <div className="stat-tile__label">{item.label}</div>
            {item.sub && <div className="stat-tile__sub">{item.sub}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
