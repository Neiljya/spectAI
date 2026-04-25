import { useState, useEffect, useCallback } from 'react';
import { supabase } from '../../lib/supabase';
import { processCoachAnalysis } from '../../lib/ai-coach';
import { DrillSandbox } from './DrillSandbox';
import { GamesenseDrillEngine } from './GamesenseDrillEngine';
import type { AimDrillTask, GamesenseConfig } from './engineTypes';
import './DrillRouter.css';

interface Props {
  userId: string;
}

type TrainingTaskType = 'aim' | 'gamesense' | 'scenario';

interface DBTask {
  id: string;
  title: string;
  description: string;
  type: TrainingTaskType;
  config: AimDrillTask | GamesenseConfig;
}

type Screen =
  | { view: 'list' }
  | { view: 'sandbox'; task: DBTask }
  | { view: 'gs'; task: DBTask }
  | { view: 'empty' };

const TYPE_BADGE: Record<string, string> = {
  aim: 'badge--red',
  gamesense: 'badge--teal',
  scenario: 'badge--teal',
};

const TYPE_ICON: Record<string, string> = {
  aim: '◎',
  gamesense: '◉',
  scenario: '◆',
};

export function DrillRouter({ userId }: Props) {
  const [screen, setScreen] = useState<Screen>({ view: 'empty' });
  const [tasks, setTasks] = useState<DBTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTasks();
  }, [userId]);

  async function loadTasks() {
    const { data, error } = await supabase
      .from('training_tasks')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false });

    if (error) {
      setError(error.message);
      return;
    }

    if (data && data.length > 0) {
      setTasks(data as DBTask[]);
      setScreen({ view: 'list' });
    } else {
      setTasks([]);
      setScreen({ view: 'empty' });
    }
  }

  async function generate() {
    setLoading(true);
    setError(null);

    try {
      await processCoachAnalysis(userId, 'training');
      await loadTasks();
      setScreen({ view: 'list' });
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function startTask(task: DBTask) {
    const cfg = task.config as any;

    if (cfg.kind === 'gamesense') {
      setScreen({ view: 'gs', task });
      return;
    }

    setScreen({ view: 'sandbox', task });
  }

  const handleDone = useCallback(() => {
    setScreen({ view: 'list' });
  }, []);

  if (screen.view === 'sandbox') {
    return (
      <div className="dr-fullscreen">
        <button className="dr-back" onClick={() => setScreen({ view: 'list' })}>
          ← Back
        </button>

        <DrillSandbox
          config={screen.task.config as AimDrillTask}
          onComplete={handleDone}
        />
      </div>
    );
  }

  if (screen.view === 'gs') {
    return (
      <div className="dr-gs-wrap">
        <div className="dr-gs-header">
          <button
            className="dr-back-inline"
            onClick={() => setScreen({ view: 'list' })}
          >
            ← Back
          </button>

          <div>
            <span className="label">Gamesense drill</span>
            <h2 className="dr-gs-title">{screen.task.title}</h2>
          </div>
        </div>

        <GamesenseDrillEngine
          config={screen.task.config as GamesenseConfig}
          onComplete={handleDone}
        />
      </div>
    );
  }

  return (
    <div className="dr-list">
      <div className="dr-list__header">
        <div>
          <span className="label">AI Coach</span>
          <h2 className="dr-list__title">Training</h2>
        </div>

        <button
          className="dr-btn dr-btn--primary"
          onClick={generate}
          disabled={loading}
        >
          {loading ? 'Generating...' : '↻ Generate drills'}
        </button>
      </div>

      {error && <div className="dr-error mono">{error}</div>}

      {loading && (
        <div className="dr-loading">
          <div className="dr-loading__spinner" />
          <span className="label">AI designing your drills...</span>
        </div>
      )}

      {!loading && tasks.length === 0 && (
        <div className="dr-empty">
          <div className="dr-empty__glyph">◎</div>
          <h3>No drills yet</h3>
          <p>
            Hit <strong>Generate drills</strong> or use{' '}
            <strong>Build Drills</strong> on the Overview tab.
          </p>
        </div>
      )}

      {!loading && tasks.length > 0 && (
        <div className="dr-tasks">
          {tasks.map((task, i) => {
            const cfg = task.config as any;
            const taskType =
              cfg.kind === 'scenario_script' ? 'scenario' : task.type;

            return (
              <div className="dr-task" key={task.id}>
                <div className="dr-task__left">
                  <div className="dr-task__num mono">0{i + 1}</div>
                  <div className="dr-task__icon">
                    {TYPE_ICON[taskType] ?? '◎'}
                  </div>
                </div>

                <div className="dr-task__body">
                  <div className="dr-task__meta">
                    <span
                      className={`badge ${
                        TYPE_BADGE[taskType] ?? 'badge--dim'
                      }`}
                    >
                      {taskType}
                    </span>

                    {cfg.arena_preset && (
                      <span className="badge badge--dim">
                        {cfg.arena_preset.replace(/_/g, ' ')}
                      </span>
                    )}

                    {cfg.kind && (
                      <span className="badge badge--dim">{cfg.kind}</span>
                    )}

                    {cfg.scenarios && (
                      <span className="badge badge--dim">
                        {cfg.scenarios.length} scenarios
                      </span>
                    )}
                  </div>

                  <h3 className="dr-task__title">
                    {cfg.drill_name ?? task.title}
                  </h3>

                  <p className="dr-task__desc">
                    {cfg.drill_instructions ?? task.description}
                  </p>
                </div>

                <button className="dr-task__start" onClick={() => startTask(task)}>
                  Start →
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}