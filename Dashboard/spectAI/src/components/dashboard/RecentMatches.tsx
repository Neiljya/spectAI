import { useEffect, useState } from 'react';
import { supabase } from '../../lib/supabase';
import type { MatchRow } from '../../types/match';
import './RecentMatches.css';

// --- HELPER FUNCTION ---
// Extracts the 11-character video ID from any standard YouTube/youtu.be link
function getYouTubeEmbedUrl(url: string): string | null {
  if (!url) return null;
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
  const match = url.match(regExp);
  return (match && match[2].length === 11) ? `https://www.youtube.com/embed/${match[2]}` : null;
}

interface Props {
  profileId: string;
  onUploadClick: () => void;
}

export function RecentMatches({ profileId, onUploadClick }: Props) {
  const [matches, setMatches] = useState<MatchRow[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<number>(0);

  useEffect(() => {
    supabase
      .from('match_data')
      .select('*')
      .eq('profile_id', profileId)
      .order('played_at', { ascending: false })
      .limit(20)
      .then(({ data }) => {
        setMatches((data ?? []) as MatchRow[]);
        setLoading(false);
      });
  }, [profileId]);

  const toggleMatch = (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
    } else {
      setExpandedId(id);
      setActiveTab(0);
    }
  };

  if (loading) {
    return (
      <div className="rm-loading">
        <div className="rm-loading__spinner" />
        <span className="label-mono">Decrypting Match History...</span>
      </div>
    );
  }

  return (
    <div className="rm-container anim-up">
      <div className="rm-header-glass">
        <div>
          <span className="eyebrow-red">Performance Archive</span>
          <h2 className="rm-title-main">Match History</h2>
        </div>
        <button className="glass-btn-primary" onClick={onUploadClick}>
          + Upload VOD
        </button>
      </div>

      {matches.length === 0 ? (
        <div className="rm-empty-glass">
          <div className="empty-glyph">◈</div>
          <h3>No Match Data</h3>
          <p className="description-text">Upload your first VOD to generate AI coaching notes.</p>
          <button className="glass-btn-primary" style={{ marginTop: '16px' }} onClick={onUploadClick}>
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
            const d = m.data;
            const outcome = m.outcome ?? '—';
            const kda = `${d.kills ?? '—'} / ${d.deaths ?? '—'} / ${d.assists ?? '—'}`;
            const score = `${d.score_us ?? '?'} – ${d.score_them ?? '?'}`;
            const cls = outcome === 'Win' ? 'win' : outcome === 'Loss' ? 'loss' : 'draw';
            
            const isExpanded = expandedId === m.id;
            const clips = Array.isArray(m.attachments) ? m.attachments.slice(0, 5) : [];
            const notes = Array.isArray(m.coach_notes) ? m.coach_notes : [];
            const hasReview = clips.length > 0 || notes.length > 0;

            // Determine if the current active clip is a YouTube link
            const currentClip = clips[activeTab];
            const ytEmbedUrl = currentClip ? getYouTubeEmbedUrl(currentClip) : null;

            return (
              <div className={`match-glass-card ${isExpanded ? 'is-expanded' : ''}`} key={m.id}>
                
                <div className="match-row-summary" onClick={() => hasReview && toggleMatch(m.id)}>
                  <span className={`rm-outcome rm-outcome--${cls}`}>{outcome}</span>
                  <span className="rm-map">{m.map ?? '—'}</span>
                  <span className="rm-agent">{m.agent ?? '—'}</span>
                  <span className="mono text-white">{score}</span>
                  <span className="mono text-dim">{kda}</span>
                  <span className="mono text-white">{d.score ?? '—'}</span>
                  <span className="mono text-teal">{d.headshot_pct != null ? `${Number(d.headshot_pct).toFixed(0)}%` : '—'}</span>
                  <span className="mono text-dim">
                    {new Date(m.played_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                  
                  <div className="rm-action-cell">
                    {hasReview ? (
                      <button className="glass-pill-btn">
                        {isExpanded ? 'Close ▴' : `${clips.length} Clips ▾`}
                      </button>
                    ) : (
                      <span className="label-mono" style={{ opacity: 0.3 }}>No VOD</span>
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="match-dropdown-content">
                    <div className="vod-review-hub">
                      
                      <div className="vod-tabs">
                        {clips.map((_, idx) => (
                          <button 
                            key={idx}
                            className={`vod-tab ${activeTab === idx ? 'active' : ''}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveTab(idx);
                            }}
                          >
                            Highlight {idx + 1}
                          </button>
                        ))}
                      </div>

                      <div className="vod-content-split">
                        
                        {/* ── THE PLAYER LOGIC FIX ── */}
                        <div className="vod-player-wrapper">
                          {currentClip ? (
                            ytEmbedUrl ? (
                              <iframe
                                className="vod-video"
                                src={ytEmbedUrl}
                                title={`VOD Highlight ${activeTab + 1}`}
                                frameBorder="0"
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                allowFullScreen
                              />
                            ) : (
                              <video 
                                src={currentClip} 
                                controls 
                                className="vod-video"
                                preload="metadata"
                              />
                            )
                          ) : (
                            <div className="vod-placeholder">No video available for this segment.</div>
                          )}
                        </div>

                        <div className="vod-notes-panel">
                          <span className="label-red">Coach Feedback</span>
                          <h4 className="notes-title">Clip Analysis {activeTab + 1}</h4>
                          <div className="notes-body">
                            {notes[activeTab] 
                              ? (typeof notes[activeTab] === 'string' ? notes[activeTab] : notes[activeTab].note || JSON.stringify(notes[activeTab])) 
                              : "No specific feedback generated for this clip yet."}
                          </div>
                        </div>

                      </div>
                    </div>
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