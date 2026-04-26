import { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { fetchTrackerProfile } from '../lib/tracker';
import { tagPlaystyle } from '../lib/playstyleTagger';
import { useAuth } from '../hooks/useAuth';

// Components
import { SkillRadar }     from '../components/dashboard/SkillRadar';
import { TrainingTab }    from '../components/dashboard/TrainingTab';
import { RecentMatches }  from '../components/dashboard/RecentMatches';
import { AIAnalysisCard } from '../components/dashboard/AIAnalysisCard';
import { PostMatchUpload } from '../components/match/PostMatchUpload';

// Types
import type { Profile, PlayerStats } from '../types/player';
import './Dashboard.css';

type Tab = 'overview' | 'analysis' | 'training' | 'profile';

const NAV: { id: Tab; label: string; glyph: string }[] = [
  { id: 'overview',  label: 'Overview',  glyph: '◈' },
  { id: 'analysis',  label: 'Analysis',  glyph: '◉' },
  { id: 'training',  label: 'Training',  glyph: '◎' },
  { id: 'profile',   label: 'Profile',   glyph: '○' },
];

const RANK_COLORS: Record<string, string> = {
  Iron: '#9FA3A8', Bronze: '#C78C5A', Silver: '#C5C5C5',
  Gold: '#D4A017', Platinum: '#2EB5CB', Diamond: '#7B6DF8',
  Ascendant: '#22C56B', Immortal: '#E84059', Radiant: '#FFFBE6',
};

function rankColor(rank: string | null) {
  if (!rank) return 'var(--t3)';
  const t = Object.keys(RANK_COLORS).find(k => rank.startsWith(k));
  return t ? RANK_COLORS[t] : 'var(--t2)';
}

export function DashboardPage() {
  const { user, loading: authLoading, signOut } = useAuth();
  const navigate = useNavigate();

  const [tab,         setTab]        = useState<Tab>('overview');
  const [profile,     setProfile]    = useState<Profile | null>(null);
  const [stats,       setStats]      = useState<PlayerStats | any>(null);
  const [loading,     setLoading]    = useState(true);
  const [syncing,     setSyncing]    = useState(false);
  const [riotInput,   setRiotInput]  = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const [error,       setError]      = useState<string | null>(null);

  // 1. Initial Load
  useEffect(() => {
    if (!user) return;
    Promise.all([
      supabase.from('profiles').select('*').eq('id', user.id).single(),
      supabase.from('player_stats').select('*').eq('profile_id', user.id)
        .order('synced_at', { ascending: false }).limit(1).maybeSingle(),
    ]).then(([p, s]) => {
      setProfile(p.data as Profile);
      setStats(s.data);
      setRiotInput((p.data as Profile)?.riot_id ?? '');
      setLoading(false);
    });
  }, [user]);

  // 2. Sync Logic (Handles API, Profile, Stats, and Match History)
  async function syncTracker() {
    if (!user || !riotInput.trim()) return;
    setSyncing(true);
    setError(null);
    try {
      const data  = await fetchTrackerProfile(riotInput.trim());
      const style = tagPlaystyle(data); 
      
      // Update basic profile info
      await supabase.from('profiles')
        .update({ riot_id: data.riot_id, avatar_url: data.avatar_url })
        .eq('id', user.id);
        
      // Sync detailed player stats
      await supabase.rpc('sync_player_stats', {
        p_profile_id: user.id,
        p_stats: {
          ...data,
          playstyle_tags: style?.tags ?? [],
          playstyle_desc: style?.desc ?? '',
          raw_tracker_data: data.raw,
        },
      });

      // Map API matches to DB schema (Excludes generated columns like 'map' to prevent 400 errors)
   // Replace the matchInserts block in Dashboard.tsx syncTracker()
// from "const matches = data.raw?.matches || [];" down to the filter

const matches = data.raw?.matches || [];
const [riotName, riotTag] = data.riot_id.split('#');

const matchInserts = matches
  .filter((m: any) =>
    m?.players?.all_players &&          // guard: skip matches with no player data
    m?.metadata?.matchid &&             // skip matches with no ID
    m?.metadata?.map                    // skip matches with no map
  )
  .map((m: any) => {
    const player = m.players.all_players.find((p: any) =>
      p.name?.toLowerCase() === riotName?.toLowerCase() &&
      p.tag?.toLowerCase()  === riotTag?.toLowerCase()
    );
    if (!player) return null;

    const team        = player.team?.toLowerCase() ?? 'red';
    const outcome     = m.teams?.[team]?.has_won ? 'Win' : 'Loss';
    const roundsPlayed = m.metadata.rounds_played || 1;
    const acs         = Math.round((player.stats?.score ?? 0) / roundsPlayed);
    const totalShots  = (player.stats?.headshots ?? 0) + (player.stats?.bodyshots ?? 0) + (player.stats?.legshots ?? 0);
    const hsPct       = totalShots > 0 ? (player.stats.headshots / totalShots) * 100 : 0;

    return {
      profile_id: user.id,
      match_id:   m.metadata.matchid,
      played_at:  new Date((m.metadata.game_start ?? 0) * 1000).toISOString(),
      schema_version: 1,
      data: {
        map:         m.metadata.map,
        agent:       player.character ?? 'Unknown',
        outcome,
        mode:        'Spike Rush',
        score_us:    m.teams?.[team]?.rounds_won  ?? 0,
        score_them:  m.teams?.[team]?.rounds_lost ?? 0,
        kills:       player.stats?.kills   ?? 0,
        deaths:      player.stats?.deaths  ?? 0,
        assists:     player.stats?.assists ?? 0,
        score:       acs,
        damage:      player.damage_made    ?? 0,
        headshot_pct: Number(hsPct.toFixed(2)),
      },
    };
  })
  .filter(Boolean);

      // Safe insert: Skip duplicates
      if (matchInserts.length > 0) {
        const { data: existing } = await supabase.from('match_data').select('match_id').eq('profile_id', user.id);
        const existingIds = new Set(existing?.map(e => e.match_id) || []);
        const newMatches = matchInserts.filter((m: any) => !existingIds.has(m.match_id));
        if (newMatches.length > 0) {
           const { error: insErr } = await supabase.from('match_data').insert(newMatches);
           if (insErr) console.error("Match Insert Fail:", insErr);
        }
      }

      // Refresh state from DB
      const { data: fresh } = await supabase.from('player_stats').select('*').eq('profile_id', user.id).maybeSingle();
      setStats(fresh);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setSyncing(false);
    }
  }

  if (authLoading || loading) return <div className="db-spin"><div className="db-spin__ring" /></div>;
  if (!user || !profile) return <Navigate to="/" replace />;

  const rrPct = Math.min(stats?.rr ?? 0, 100);

  return (
    <div className="db db-themed-bg">

      {/* ── Sidebar ── */}
      <aside className="db-side glass-panel">
        <div className="db-side__logo" onClick={() => navigate('/')}>
          SPECT<span>AI</span>
        </div>

        <nav className="db-side__nav">
          {NAV.map(n => (
            <button
              key={n.id}
              className={`db-nav ${tab === n.id ? 'db-nav--active' : ''}`}
              onClick={() => { setTab(n.id); setShowUpload(false); }}
            >
              <span className="db-nav__glyph">{n.glyph}</span>
              <span className="db-nav__label">{n.label}</span>
              {tab === n.id && <span className="db-nav__pip" />}
            </button>
          ))}
        </nav>

        {stats?.current_rank && (
          <div className="db-side__rank glass-card">
            <span className="label">Current Rating</span>
            {stats.rank_image_url && (
               <img src={stats.rank_image_url} alt={stats.current_rank} className="db-side__rank-badge" />
            )}
            <div style={{ width: '100%', textAlign: 'center' }}>
              <span className="db-side__rank-name mono" style={{ color: rankColor(stats.current_rank) }}>
                {stats.current_rank}
              </span>
            </div>
            <div className="db-side__rr-track">
              <div className="db-side__rr-fill" style={{ width: `${rrPct}%`, background: rankColor(stats.current_rank) }} />
            </div>
            <span className="label">{stats.rr ?? 0} RR</span>
          </div>
        )}
      </aside>

      {/* ── Main ── */}
      <main className="db-main">
        <header className="db-top glass-panel">
          <div className="db-top__breadcrumb">
            <span className="label">spectai</span>
            <span className="db-top__sep">/</span>
            <span className="label" style={{ color: 'var(--t1)' }}>{tab}</span>
          </div>
          <div className="db-top__right">
            {error && <span className="db-top__error mono">{error}</span>}
            <span className="db-top__user mono">{profile.username}</span>
            <button className="glass-btn-small" onClick={() => signOut()}>Sign out</button>
          </div>
        </header>

        <div className="db-body">

          {/* ══ OVERVIEW ══ */}
          {tab === 'overview' && (
            <div className="db-overview">
              {/* Profile Banner */}
              <div className="db-card db-player glass-card anim-up">
                <div className="db-player__left">
                  <div className="db-player__avatar">
                    {profile.avatar_url
                      ? <img src={profile.avatar_url} alt="Avatar" />
                      : <span>{profile.username[0].toUpperCase()}</span>
                    }
                  </div>
                  <div className="db-player__info">
                    <div className="db-player__name">{profile.username}</div>
                    <div className="db-player__riot mono">{profile.riot_id ?? 'No Riot ID linked'}</div>
                  </div>
                </div>
                <div className="db-player__sync">
                  <input
                    className="glass-input"
                    value={riotInput}
                    onChange={e => setRiotInput(e.target.value)}
                    placeholder="Name#TAG"
                    onKeyDown={e => e.key === 'Enter' && syncTracker()}
                  />
                  <button className="glass-btn" onClick={syncTracker} disabled={syncing}>
                    {syncing ? 'Syncing...' : '↻ Sync Data'}
                  </button>
                </div>
              </div>

              {/* Lifetime Stats Grid */}
              <div className="db-tiles anim-up-1">
                {[
                  { label: 'Elo Rating',  value: String(stats?.elo ?? '—'),           hot: (stats?.elo ?? 0) > 1500 },
                  { label: 'Win Rate',    value: stats?.win_rate ? `${Number(stats.win_rate).toFixed(1)}%` : '—', hot: (stats?.win_rate ?? 0) >= 50 },
                  { label: 'Life. Games', value: String(stats?.lifetime_games ?? '—'), hot: false },
                  { label: 'Life. Wins',  value: String(stats?.lifetime_wins ?? '—'),  hot: false },
                  { label: 'Peak Rank',   value: stats?.peak_rank ?? '—',              hot: false },
                  { label: 'Last Match',  value: (stats?.last_mmr_change ?? 0) > 0 ? `+${stats?.last_mmr_change}` : String(stats?.last_mmr_change ?? '—'), hot: (stats?.last_mmr_change ?? 0) > 0 },
                ].map(s => (
                  <div className="db-tile glass-card" key={s.label}>
                    <div className={`db-tile__val mono ${s.hot ? 'db-tile__val--hot' : ''}`}>{s.value}</div>
                    <div className="db-tile__label label">{s.label}</div>
                  </div>
                ))}
              </div>

              {/* Radar + AI Analysis Row */}
              <div className="db-lower anim-up-2">
                <div className="db-card glass-card db-card--radar">
                  <span className="label">Skill Profile</span>
                  {stats ? <SkillRadar stats={stats} /> : <p className="label">Sync to view web.</p>}
                </div>
                
                <div className="db-analysis-col">
                  {/* Real-time AI Summary & Agent Trigger */}
<AIAnalysisCard userId={profile.id} />

                  {/* Top Agents Cards */}
                  {stats?.agent_prefs && (
                    <div className="db-agents-grid">
                      {stats.agent_prefs.slice(0, 3).map((agent: any) => (
                        <div className="agent-card glass-card" key={agent.name}>
                          <div className="agent-card__header">
                            <h4 className="agent-card__name">{agent.name}</h4>
                            <span className="glass-badge badge--dim">{agent.role}</span>
                          </div>
                          <div className="agent-card__stats">
                            <div className="ac-stat"><span className="ac-stat__lbl">K/D</span><span className="ac-stat__val mono">{agent.kd.toFixed(2)}</span></div>
                            <div className="ac-stat"><span className="ac-stat__lbl">WR</span><span className="ac-stat__val mono">{agent.win_rate.toFixed(0)}%</span></div>
                            <div className="ac-stat"><span className="ac-stat__lbl">HRS</span><span className="ac-stat__val mono">{agent.hours}</span></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ══ ANALYSIS ══ */}
          {tab === 'analysis' && (
            <div className="anim-up">
              {showUpload
                ? <PostMatchUpload
                    profileId={profile.id}
                    onSuccess={() => setShowUpload(false)}
                    onCancel={() => setShowUpload(false)}
                  />
                : <RecentMatches
                    profileId={profile.id}
                    onUploadClick={() => setShowUpload(true)}
                  />
              }
            </div>
          )}

          {/* ══ TRAINING ══ */}
          {tab === 'training' && <div className="anim-up"><TrainingTab stats={stats} /></div>}

          {/* ══ PROFILE ══ */}
          {tab === 'profile' && (
            <div className="db-profile anim-up">
              <span className="label">Account</span>
              <h2 className="db-profile__title">Profile</h2>
              <div className="db-profile__rows glass-card">
                {[
                  { label: 'Username',     value: profile.username },
                  { label: 'Riot ID',      value: profile.riot_id ?? 'Not linked' },
                  { label: 'Region',       value: profile.region.toUpperCase() },
                  { label: 'Member since', value: new Date(profile.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' }) },
                ].map(r => (
                  <div className="db-profile__row" key={r.label}>
                    <span className="label">{r.label}</span>
                    <span className="mono db-profile__val">{r.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}