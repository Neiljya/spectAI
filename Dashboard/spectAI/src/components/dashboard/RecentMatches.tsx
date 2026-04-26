// src/components/dashboard/RecentMatches.tsx
import { useEffect, useState } from 'react';
import { supabase } from '../../lib/supabase';
import type { MatchRow, CoachNotes, ClipNote } from '../../types/match';
import './RecentMatches.css';

function getYouTubeEmbedUrl(url: string): string | null {
  const match = url.match(/^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/);
  return match && match[2].length === 11
    ? `https://www.youtube.com/embed/${match[2]}`
    : null;
}

// attachments is a plain text column — parse it as JSON array if possible,
// otherwise treat as single URL
function parseAttachments(raw: unknown): string[] {
  if (!raw) return [];
  // Already an array (Supabase may return jsonb arrays directly)
  if (Array.isArray(raw)) return (raw as string[]).filter(Boolean);
  // String — try JSON parse first, then comma-split
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed;
    } catch (_) {}
    return raw.split(',').map(s => s.trim()).filter(Boolean);
  }
  return [];
}

interface Props {
  profileId:     string;
  onUploadClick: () => void;
}

export function RecentMatches({ profileId, onUploadClick }: Props) {
  const [matches,    setMatches]    = useState<MatchRow[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeClip, setActiveClip] = useState(0);

  useEffect(() => {
    supabase
      .from('match_data')
      .select('*')
      .eq('profile_id', profileId)
      .order('played_at', { ascending: false })
      .limit(20)
      .then(({ data, error }) => {
        if (error) console.error('RecentMatches:', error);
        setMatches((data ?? []) as MatchRow[]);
        setLoading(false);
      });
  }, [profileId]);

  function toggle(id: string) {
    if (expandedId === id) { setExpandedId(null); }
    else { setExpandedId(id); setActiveClip(0); }
  }

  if (loading) return (
    <div className="rm-loading">
      <div className="rm-loading__spinner" />
      <span className="label">Loading match history...</span>
    </div>
  );

  return (
    <div className="rm-container anim-up">
      <div className="rm-header-glass">
        <div>
          <span className="eyebrow-red">Performance Archive</span>
          <h2 className="rm-title-main">Match History</h2>
        </div>
        <button className="glass-btn-primary" onClick={onUploadClick}>+ Upload Match</button>
      </div>

      {matches.length === 0 ? (
        <div className="rm-empty-glass">
          <div className="empty-glyph">◈</div>
          <h3>No Match Data</h3>
          <p>Sync your Riot ID or upload a match manually.</p>
          <button className="glass-btn-primary" style={{ marginTop: 16 }} onClick={onUploadClick}>
            Upload Match
          </button>
        </div>
      ) : (
        <div className="rm-list">
          <div className="rm-list-header">
            <span>Result</span>
            <span>Map</span>
            <span>Agent</span>
            <span>Score</span>
            <span>K / D / A</span>
            <span>ACS</span>
            <span>HS%</span>
            <span>Date</span>
            <span style={{ textAlign: 'right' }}>Review</span>
          </div>

          {matches.map(m => {
            // ── Read stats from data JSONB ───────────────────────
            const d = m.data ?? {};

            // Generated columns (map/agent/outcome) are stored on m directly.
            // Fall back to data JSONB for rows imported before generated cols existed.
            const map     = m.map     ?? (d.map     as string) ?? '—';
            const agent   = m.agent   ?? (d.agent   as string) ?? '—';
            const outcome = m.outcome ?? (d.outcome as string) ?? '—';
            const cls     = outcome === 'Win' ? 'win' : outcome === 'Loss' ? 'loss' : 'draw';
            const kda     = `${d.kills ?? '—'} / ${d.deaths ?? '—'} / ${d.assists ?? '—'}`;
            const score   = `${d.score_us ?? '?'} – ${d.score_them ?? '?'}`;

            // ── coach_notes JSONB ───────────────────────────────
            const notes: CoachNotes = (m.coach_notes as CoachNotes) ?? {};
            const clipNotes: ClipNote[] = notes.clip_notes ?? [];

            // ── attachments (plain text column) ────────────────
            // Separate from clip_notes — raw attachment URLs with no AI comment
            const attachmentUrls = parseAttachments(m.attachments);

            // ── performance_summary (plain text column) ─────────
            const perfSummary = m.performance_summary;

            const hasReview = !!(
              notes.summary ||
              clipNotes.length > 0 ||
              attachmentUrls.length > 0 ||
              perfSummary
            );

            const isExpanded = expandedId === m.id;

            // Merge clip_notes + raw attachments into one clip list for the player
            // clip_notes take priority (they have comments); raw attachments shown after
            const allClips: { url: string; comment?: string }[] = [
              ...clipNotes,
              ...attachmentUrls
                .filter(url => !clipNotes.find(c => c.url === url))
                .map(url => ({ url })),
            ];

            const current  = allClips[activeClip];
            const ytEmbed  = current ? getYouTubeEmbedUrl(current.url) : null;

            return (
              <div className={`match-glass-card ${isExpanded ? 'is-expanded' : ''}`} key={m.id}>

                {/* ── Summary row ── */}
                <div
                  className="match-row-summary"
                  onClick={() => toggle(m.id)}
                  style={{ cursor: hasReview ? 'pointer' : 'default' }}
                >
                  <span className={`rm-outcome rm-outcome--${cls}`}>{outcome}</span>
                  <span className="rm-map">{map}</span>
                  <span className="rm-agent">{agent}</span>
                  <span className="mono">{score}</span>
                  <span className="mono text-dim">{kda}</span>
                  <span className="mono">{d.score ?? '—'}</span>
                  <span className="mono">
                    {d.headshot_pct != null ? `${Number(d.headshot_pct).toFixed(0)}%` : '—'}
                  </span>
                  <span className="mono text-dim">
                    {new Date(m.played_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                  <div className="rm-action-cell">
                    {hasReview ? (
                      <button className="glass-pill-btn">
                        {isExpanded
                          ? 'Close ▴'
                          : `Review${allClips.length > 0 ? ` · ${allClips.length} clips` : ''} ▾`}
                      </button>
                    ) : (
                      <span className="label" style={{ opacity: 0.3 }}>No Review</span>
                    )}
                  </div>
                </div>

                {/* ── Expanded section ── */}
                {isExpanded && (
                  <div className="match-dropdown-content">

                    {/* Performance summary (plain text column) */}
                    {perfSummary && (
                      <div className="notes-summary-section">
                        <span className="label" style={{ color: 'var(--red)', marginBottom: 6, display: 'block' }}>
                          Performance Summary
                        </span>
                        <p className="notes-summary-text">{perfSummary}</p>
                      </div>
                    )}

                    {/* AI coach notes: summary + strengths/weaknesses */}
                    {(notes.summary || notes.strengths || notes.weaknesses) && (
                      <div className="notes-summary-section">
                        {notes.summary && (
                          <>
                            <span className="label" style={{ color: 'var(--red)', marginBottom: 6, display: 'block' }}>
                              Coach Analysis
                            </span>
                            <p className="notes-summary-text">{notes.summary}</p>
                          </>
                        )}
                        <div className="notes-sw-grid">
                          {notes.strengths && notes.strengths.length > 0 && (
                            <div className="notes-sw-col">
                              <span className="label" style={{ color: 'var(--teal)', marginBottom: 8, display: 'block' }}>
                                Strengths
                              </span>
                              <ul className="notes-bullet-list notes-bullet-list--green">
                                {notes.strengths.map((s, i) => <li key={i}>{s}</li>)}
                              </ul>
                            </div>
                          )}
                          {notes.weaknesses && notes.weaknesses.length > 0 && (
                            <div className="notes-sw-col">
                              <span className="label" style={{ color: 'var(--red)', marginBottom: 8, display: 'block' }}>
                                Weaknesses
                              </span>
                              <ul className="notes-bullet-list notes-bullet-list--red">
                                {notes.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                              </ul>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Clip player */}
                    {allClips.length > 0 && (
                      <div className="vod-review-hub">
                        <span className="label" style={{ color: 'var(--red)', marginBottom: 10, display: 'block' }}>
                          Clip Review
                        </span>

                        <div className="vod-tabs">
                          {allClips.map((_, idx) => (
                            <button
                              key={idx}
                              className={`vod-tab ${activeClip === idx ? 'active' : ''}`}
                              onClick={e => { e.stopPropagation(); setActiveClip(idx); }}
                            >
                              Clip {idx + 1}
                            </button>
                          ))}
                        </div>

                        <div className="vod-content-split">
                          <div className="vod-player-wrapper">
                            {current ? (
                              ytEmbed ? (
                                <iframe
                                  className="vod-video"
                                  src={ytEmbed}
                                  title={`Clip ${activeClip + 1}`}
                                  frameBorder="0"
                                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                  allowFullScreen
                                />
                              ) : (
                                <video
                                  key={current.url}
                                  src={current.url}
                                  controls
                                  className="vod-video"
                                  preload="metadata"
                                />
                              )
                            ) : (
                              <div className="vod-placeholder">No video available.</div>
                            )}
                          </div>

                          {/* Per-clip label/comment */}
                          <div className="vod-notes-panel">
                            <span className="label" style={{ color: 'var(--red)', marginBottom: 6, display: 'block' }}>
                              Coach Note — Clip {activeClip + 1}
                            </span>
                            <p className="notes-body">
                              {current?.comment ?? 'No comment for this clip.'}
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}