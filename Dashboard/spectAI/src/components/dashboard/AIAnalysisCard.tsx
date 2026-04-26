// src/components/dashboard/AIAnalysisCard.tsx
// Shows AI summary on the Overview tab.
// "Regenerate Analysis" refreshes ai_summaries.
// "Build Drills" writes tasks to Supabase in the format DrillRouter expects.

import { useEffect, useState } from 'react';
import { supabase } from '../../lib/supabase';
import { processCoachAnalysis, type AIResponse } from '../../lib/ai-coach';
import './AIAnalysisCard.css';

interface Props {
  userId: string;
}

export function AIAnalysisCard({ userId }: Props) {
  const [data, setData] = useState<AIResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null);

  const [isBuilding, setIsBuilding] = useState(false);
  const [buildMsg, setBuildMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;

    async function load() {
      setLoading(true);

      const { data: saved } = await supabase
        .from('ai_summaries')
        .select('*')
        .eq('profile_id', userId)
        .maybeSingle();

      if (saved) {
        setData({
          summary: saved.summary,
          strengths: saved.strengths,
          weaknesses: saved.weaknesses,
        });

        setLoading(false);
        return;
      }

      try {
        const fresh = await processCoachAnalysis(userId, 'summary');
        setData(fresh);
      } catch (err) {
        console.error('Initial summary generation failed:', err);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [userId]);

  async function handleRegenerateAnalysis() {
    if (isRefreshing || !userId) return;

    setIsRefreshing(true);
    setRefreshMsg(null);
    setBuildMsg(null);

    try {
      const fresh = await processCoachAnalysis(userId, 'summary');
      setData(fresh);
      setRefreshMsg('Analysis regenerated from latest data.');
    } catch (err: unknown) {
      setRefreshMsg(`Failed: ${(err as Error).message}`);
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleBuildSkills() {
    if (isBuilding || !userId) return;

    setIsBuilding(true);
    setBuildMsg(null);
    setRefreshMsg(null);

    try {
      await processCoachAnalysis(userId, 'training');
      setBuildMsg('Drills generated. Go to Training tab to start.');
    } catch (err: unknown) {
      setBuildMsg(`Failed: ${(err as Error).message}`);
    } finally {
      setIsBuilding(false);
    }
  }

  if (loading && !data) {
    return (
      <div className="ai-card ai-card--loading">
        <div className="ai-card__spinner" />
        <span className="label">Consulting AI coach...</span>
      </div>
    );
  }

  return (
    <div className="ai-card anim-up">
      <div className="ai-card__header">
        <div>
          <span className="label">AI Coach</span>
          <h2 className="ai-card__title">Match Intelligence</h2>
        </div>

        <div className="ai-card__actions">
          <button
            className={`ai-card__refresh-btn ${
              isRefreshing ? 'ai-card__refresh-btn--busy' : ''
            }`}
            onClick={handleRegenerateAnalysis}
            disabled={isRefreshing || isBuilding}
            title="Regenerate analysis using latest match/stat data"
          >
            {isRefreshing ? (
              <>
                <span className="ai-card__btn-spinner" /> Regenerating...
              </>
            ) : (
              '↻ Regenerate'
            )}
          </button>

          <button
            className={`ai-card__build-btn ${
              isBuilding ? 'ai-card__build-btn--busy' : ''
            }`}
            onClick={handleBuildSkills}
            disabled={isBuilding || isRefreshing}
          >
            {isBuilding ? (
              <>
                <span className="ai-card__btn-spinner" /> Building...
              </>
            ) : (
              '◈ Build Drills'
            )}
          </button>
        </div>
      </div>

      <div className="ai-card__summary">
        <p>
          {data?.summary ??
            'No analysis yet. Upload matches and sync tracker.gg first.'}
        </p>
      </div>

      {refreshMsg && (
        <div
          className={`ai-card__msg ${
            refreshMsg.startsWith('Failed')
              ? 'ai-card__msg--err'
              : 'ai-card__msg--ok'
          }`}
        >
          {refreshMsg}
        </div>
      )}

      {buildMsg && (
        <div
          className={`ai-card__msg ${
            buildMsg.startsWith('Failed')
              ? 'ai-card__msg--err'
              : 'ai-card__msg--ok'
          }`}
        >
          {buildMsg}
        </div>
      )}

      {data?.strengths?.length || data?.weaknesses?.length ? (
        <div className="ai-card__grid">
          <div className="ai-card__col">
            <span
              className="label"
              style={{
                color: 'var(--teal)',
                marginBottom: '10px',
                display: 'block',
              }}
            >
              Strengths
            </span>

            <ul className="ai-card__list ai-card__list--green">
              {data?.strengths?.map(s => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>

          <div className="ai-card__col">
            <span
              className="label"
              style={{
                color: 'var(--red)',
                marginBottom: '10px',
                display: 'block',
              }}
            >
              Weaknesses
            </span>

            <ul className="ai-card__list ai-card__list--red">
              {data?.weaknesses?.map(w => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </div>
  );
}