// src/components/dashboard/PlayerHeader.tsx
import { useState } from 'react';
import type { Profile, PlayerStats } from '@/types/player';
import './PlayerHeader.css';

interface Props {
  profile: Profile;
  stats: PlayerStats | any; // Allows rank_image_url
  syncing: boolean;
  onSync: (riotId: string) => void;
}

const RANK_COLORS: Record<string, string> = {
  Iron: '#9FA3A8', Bronze: '#C78C5A', Silver: '#C5C5C5',
  Gold: '#F0A500', Platinum: '#2EB5CB', Diamond: '#7B6DF8',
  Ascendant: '#22C56B', Immortal: '#E84059', Radiant: '#FFFBE6',
};

function rankColor(rank: string | null): string {
  if (!rank) return 'rgba(255, 255, 255, 0.4)';
  const tier = Object.keys(RANK_COLORS).find(k => rank.startsWith(k));
  return tier ? RANK_COLORS[tier] : 'rgba(255, 255, 255, 0.6)';
}

export function PlayerHeader({ profile, stats, syncing, onSync }: Props) {
  const [riotInput, setRiotInput] = useState(profile.riot_id ?? '');
  const [editMode, setEditMode]   = useState(!profile.riot_id);

  function handleSync() {
    if (!riotInput.trim()) return;
    onSync(riotInput.trim());
    setEditMode(false);
  }

  const rrPct = stats?.rr != null ? Math.min((stats.rr / 100) * 100, 100) : 0;
  const rColor = rankColor(stats?.current_rank ?? null);

  return (
    <div className="player-header fade-up">
      
      {/* ── Left: Identity ── */}
      <div className="player-header__identity">
        <div className="player-header__avatar">
          {profile.avatar_url
            ? <img src={profile.avatar_url} alt={profile.username} />
            : <span className="player-header__avatar-fallback">{profile.username[0].toUpperCase()}</span>
          }
          <div className="player-header__avatar-ring" />
        </div>

        <div className="player-header__info">
          <div className="player-header__username">{profile.username}</div>

          {editMode ? (
            <div className="player-header__riot-input">
              <input
                type="text"
                value={riotInput}
                onChange={e => setRiotInput(e.target.value)}
                placeholder="Name#TAG"
                onKeyDown={e => e.key === 'Enter' && handleSync()}
                autoFocus
              />
              <button onClick={handleSync} disabled={syncing}>
                {syncing ? '...' : 'Sync'}
              </button>
            </div>
          ) : (
            <button className="player-header__riot-id mono" onClick={() => setEditMode(true)}>
              {profile.riot_id ?? '+ Link Riot ID'}
            </button>
          )}

          <div className="player-header__region">
            <span className="glass-badge badge--dim">{profile.region.toUpperCase()}</span>
          </div>
        </div>
      </div>

      {/* ── Center: Rank ── */}
      <div className="player-header__rank">
        <div className="player-header__rank-display">
          {stats?.rank_image_url && (
            <img src={stats.rank_image_url} alt="Rank Badge" className="player-header__rank-badge" />
          )}
          <div className="player-header__rank-text">
            <div 
              className="player-header__rank-name"
              style={{ 
                color: rColor, 
                textShadow: `0 0 20px ${rColor}40` 
              }}
            >
              {stats?.current_rank ?? 'Unranked'}
            </div>
            {stats?.peak_rank && stats.peak_rank !== stats.current_rank && (
              <div className="player-header__peak">
                <span style={{ color: 'var(--t3)' }}>Peak:</span>
                <span style={{ color: rankColor(stats.peak_rank) }}>{stats.peak_rank}</span>
              </div>
            )}
          </div>
        </div>

        {stats?.current_rank && (
          <div className="player-header__rr-bar">
            <div className="player-header__rr-track">
              <div 
                className="player-header__rr-fill" 
                style={{ 
                  width: `${rrPct}%`, 
                  background: rColor,
                  boxShadow: `0 0 10px ${rColor}80` 
                }} 
              />
            </div>
            <span className="player-header__rr-label mono">{stats?.rr ?? 0} RR</span>
          </div>
        )}
      </div>

      {/* ── Right: Quick Stats ── */}
      <div className="player-header__quick-stats">
        <QuickStat label="K/D"    value={stats?.kd_ratio?.toFixed(2) ?? '—'} accent={stats?.kd_ratio != null && stats.kd_ratio >= 1.2} />
        <QuickStat label="WR"     value={stats?.win_rate != null ? `${stats.win_rate.toFixed(1)}%` : '—'} accent={stats?.win_rate != null && stats.win_rate >= 50} />
        <QuickStat label="ACS"    value={stats?.avg_score?.toFixed(0) ?? '—'} />
        <QuickStat label="DMG/R"  value={stats?.avg_damage?.toFixed(0) ?? '—'} />
      </div>

      {/* ── Absolute Top Right: Sync Status ── */}
      {stats && (
        <div className="player-header__sync-info">
          <span className="player-header__sync-time">
            Updated {new Date(stats.synced_at).toLocaleDateString()}
          </span>
          <button className="glass-btn-small" onClick={() => setEditMode(true)} disabled={syncing}>
            {syncing ? 'Syncing...' : '↻ Refresh'}
          </button>
        </div>
      )}
    </div>
  );
}

function QuickStat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="quick-stat-glass">
      <span className="quick-stat__label">{label}</span>
      <span className={`quick-stat__value mono ${accent ? 'quick-stat__value--accent' : ''}`}>{value}</span>
    </div>
  );
}