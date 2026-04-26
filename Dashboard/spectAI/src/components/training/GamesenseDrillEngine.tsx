// src/components/training/GamesenseDrillEngine.tsx
// Overhead 2D tactical scenario trainer.
// Shows intel, asks for a decision under time pressure, then shows reasoning.

import { useState, useEffect, useRef, useCallback } from 'react';
import type { GamesenseConfig, GamesenseScenario } from '../../lib/gemini';
import './GamesenseDrillEngine.css';

// ── Static map outlines (simplified SVG paths for each map) ─

const MAP_LAYOUTS: Record<string, { viewBox: string; paths: { d: string; label: string; x: number; y: number }[] }> = {
  Ascent: {
    viewBox: '0 0 300 260',
    paths: [
      { d: 'M20 20 H130 V100 H80 V140 H20Z',         label: 'A Site',  x: 50,  y: 80  },
      { d: 'M170 20 H280 V100 H230 V140 H170Z',       label: 'B Site',  x: 200, y: 80  },
      { d: 'M80 140 H230 V200 H150 V240 H80Z',        label: 'Mid',     x: 150, y: 175 },
      { d: 'M130 60 H170 V120 H130Z',                 label: 'Market',  x: 148, y: 90  },
    ],
  },
  Bind: {
    viewBox: '0 0 300 260',
    paths: [
      { d: 'M20 20 H120 V110 H60 V160 H20Z',          label: 'A Site',  x: 55,  y: 85  },
      { d: 'M180 20 H280 V110 H220 V160 H180Z',       label: 'B Site',  x: 215, y: 85  },
      { d: 'M60 160 H120 V240 H60Z',                  label: 'Short',   x: 88,  y: 200 },
      { d: 'M180 160 H240 V240 H180Z',                label: 'Long',    x: 208, y: 200 },
      { d: 'M120 100 H180 V180 H120Z',                label: 'Hookah',  x: 148, y: 140 },
    ],
  },
  Haven: {
    viewBox: '0 0 340 260',
    paths: [
      { d: 'M10 20 H100 V120 H10Z',                   label: 'A Site',  x: 54,  y: 70  },
      { d: 'M120 20 H220 V120 H120Z',                 label: 'B Site',  x: 168, y: 70  },
      { d: 'M240 20 H330 V120 H240Z',                 label: 'C Site',  x: 284, y: 70  },
      { d: 'M10 140 H330 V200 H10Z',                  label: 'Mid',     x: 168, y: 168 },
    ],
  },
  default: {
    viewBox: '0 0 300 260',
    paths: [
      { d: 'M20 20 H130 V130 H20Z',                   label: 'A Site',  x: 75,  y: 75  },
      { d: 'M170 20 H280 V130 H170Z',                 label: 'B Site',  x: 225, y: 75  },
      { d: 'M80 150 H220 V240 H80Z',                  label: 'Mid',     x: 150, y: 195 },
    ],
  },
};

function getLayout(map: string) {
  return MAP_LAYOUTS[map] ?? MAP_LAYOUTS.default;
}

// ── Minimap SVG ────────────────────────────────────────────

function MiniMap({ scenario, phase }: { scenario: GamesenseScenario; phase: 'thinking' | 'result' }) {
  const layout = getLayout(scenario.map);

  // Fake player dot — always near bottom center of map
  const playerPos = { x: 148, y: 215 };
  // Fake enemy dots — visible only partially (fog of war)
  const enemyHints = [
    { x: 60,  y: 60,  visible: phase === 'result' },
    { x: 210, y: 40,  visible: false },
    { x: 150, y: 110, visible: true  },
  ];

  return (
    <div className="gs-minimap">
      <span className="label" style={{ marginBottom: '8px', display: 'block' }}>
        {scenario.map} — Overhead View
      </span>
      <svg viewBox={layout.viewBox} width="100%" className="gs-minimap__svg">
        {/* Map zones */}
        {layout.paths.map((p, i) => (
          <g key={i}>
            <path d={p.d} fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
            <text x={p.x} y={p.y} fontSize="9" fill="rgba(255,255,255,0.3)"
              textAnchor="middle" fontFamily="Share Tech Mono, monospace"
              letterSpacing="0.08em">
              {p.label.toUpperCase()}
            </text>
          </g>
        ))}

        {/* Fog of war overlay */}
        <rect width="100%" height="100%" fill="rgba(5,6,7,0.35)" />

        {/* Enemy dots */}
        {enemyHints.filter(e => e.visible).map((e, i) => (
          <g key={i}>
            <circle cx={e.x} cy={e.y} r="6" fill="rgba(232,58,58,0.25)" />
            <circle cx={e.x} cy={e.y} r="3.5" fill="#E83A3A" />
          </g>
        ))}

        {/* ? markers for unknown enemies */}
        {enemyHints.filter(e => !e.visible).map((e, i) => (
          <text key={i} x={e.x} y={e.y + 4} fontSize="11" fill="rgba(232,58,58,0.3)"
            textAnchor="middle" fontFamily="Share Tech Mono, monospace">?</text>
        ))}

        {/* Player dot */}
        <circle cx={playerPos.x} cy={playerPos.y} r="7" fill="rgba(29,200,160,0.2)" />
        <circle cx={playerPos.x} cy={playerPos.y} r="4" fill="var(--teal)" />
        <circle cx={playerPos.x} cy={playerPos.y} r="1.5" fill="#fff" />

        {/* Direction cone */}
        <path
          d={`M${playerPos.x} ${playerPos.y} L${playerPos.x - 10} ${playerPos.y - 22} L${playerPos.x + 10} ${playerPos.y - 22}Z`}
          fill="rgba(29,200,160,0.15)"
          stroke="rgba(29,200,160,0.3)"
          strokeWidth="0.5"
        />
      </svg>

      <div className="gs-minimap__legend">
        <div className="gs-minimap__legend-item">
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--teal)' }} />
          <span className="label">You</span>
        </div>
        <div className="gs-minimap__legend-item">
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--red)' }} />
          <span className="label">Known enemy</span>
        </div>
        <div className="gs-minimap__legend-item">
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'rgba(232,58,58,0.4)' }}>?</span>
          <span className="label">Unknown</span>
        </div>
      </div>
    </div>
  );
}

// ── Timer ring ─────────────────────────────────────────────

function TimerRing({ total, remaining }: { total: number; remaining: number }) {
  const r  = 22;
  const c  = 2 * Math.PI * r;
  const pct = remaining / total;
  const color = pct > 0.5 ? 'var(--teal)' : pct > 0.25 ? 'var(--gold)' : 'var(--red)';

  return (
    <div className="gs-timer">
      <svg width="60" height="60" viewBox="0 0 60 60">
        <circle cx="30" cy="30" r={r} fill="none" stroke="var(--b2)" strokeWidth="3" />
        <circle
          cx="30" cy="30" r={r}
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          strokeLinecap="round"
          transform="rotate(-90 30 30)"
          style={{ transition: 'stroke-dashoffset 1s linear, stroke 0.3s' }}
        />
        <text x="30" y="35" textAnchor="middle" fontSize="14" fontFamily="Share Tech Mono, monospace"
          fill={color}>{remaining}</text>
      </svg>
    </div>
  );
}

// ── Scenario view ──────────────────────────────────────────

function ScenarioView({
  scenario,
  index,
  total,
  onAnswer,
}: {
  scenario: GamesenseScenario;
  index: number;
  total: number;
  onAnswer: (correct: boolean, label: string) => void;
}) {
  const [timeLeft,  setTimeLeft]  = useState(scenario.time_limit_seconds);
  const [phase,     setPhase]     = useState<'thinking' | 'result'>('thinking');
  const [picked,    setPicked]    = useState<string | null>(null);
  const [correct,   setCorrect]   = useState<boolean | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function startTimer() {
    timerRef.current = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) {
          clearInterval(timerRef.current!);
          // Time out — pick nothing, mark wrong
          setPhase('result');
          setCorrect(false);
          onAnswer(false, 'TIME OUT');
          return 0;
        }
        return t - 1;
      });
    }, 1000);
  }

  useEffect(() => {
    startTimer();
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  function handlePick(label: string, isCorrect: boolean) {
    if (phase === 'result') return;
    clearInterval(timerRef.current!);
    setPicked(label);
    setCorrect(isCorrect);
    setPhase('result');
    onAnswer(isCorrect, label);
  }

  const correctOption = scenario.options.find(o => o.is_correct);

  return (
    <div className="gs-scenario anim-up">
      {/* Progress */}
      <div className="gs-progress">
        <span className="label">Scenario {index + 1} of {total}</span>
        <div className="gs-progress__track">
          <div className="gs-progress__fill" style={{ width: `${((index) / total) * 100}%` }} />
        </div>
        <TimerRing total={scenario.time_limit_seconds} remaining={timeLeft} />
      </div>

      <div className="gs-layout">
        {/* Left: minimap */}
        <MiniMap scenario={scenario} phase={phase} />

        {/* Right: intel + options */}
        <div className="gs-right">
          {/* Situation */}
          <div className="gs-situation">
            <div className="gs-situation__meta">
              <span className="badge badge--dim">{scenario.map}</span>
              <span className="badge badge--dim">{scenario.round_type.replace('_', ' ')}</span>
              <span className="badge badge--red">{scenario.your_role}</span>
            </div>
            <p className="gs-situation__text">{scenario.situation}</p>
          </div>

          {/* Intel */}
          <div className="gs-intel">
            <span className="label" style={{ marginBottom: '8px', display: 'block' }}>Intel</span>
            {scenario.intel.map((info, i) => (
              <div className="gs-intel__item" key={i}>
                <span className="gs-intel__bullet mono">→</span>
                <span className="gs-intel__text">{info}</span>
              </div>
            ))}
          </div>

          {/* Options */}
          <div className="gs-options">
            <span className="label" style={{ marginBottom: '10px', display: 'block' }}>
              {phase === 'thinking' ? 'What do you do?' : 'Result'}
            </span>
            {scenario.options.map((opt, i) => {
              let state = 'idle';
              if (phase === 'result') {
                if (opt.label === picked) state = opt.is_correct ? 'correct' : 'wrong';
                else if (opt.is_correct) state = 'reveal';
              }

              return (
                <button
                  key={i}
                  className={`gs-option gs-option--${state}`}
                  onClick={() => handlePick(opt.label, opt.is_correct)}
                  disabled={phase === 'result'}
                >
                  <span className="gs-option__label">{opt.label}</span>
                  {phase === 'result' && (opt.label === picked || opt.is_correct) && (
                    <span className="gs-option__reasoning">{opt.reasoning}</span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Next button */}
          {phase === 'result' && (
            <div className="gs-result-bar">
              <span className={`gs-result-bar__verdict ${correct ? 'gs-result-bar__verdict--correct' : 'gs-result-bar__verdict--wrong'}`}>
                {timeLeft === 0 ? 'Time out' : correct ? 'Correct' : 'Wrong'}
              </span>
              {correct
                ? <span className="gs-result-bar__hint">Good read. {correctOption?.reasoning}</span>
                : <span className="gs-result-bar__hint">Correct: {correctOption?.label}</span>
              }
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main engine ────────────────────────────────────────────

interface Props {
  config: GamesenseConfig;
  onComplete: (stats: { correct: number; total: number; score: number }) => void;
}

export function GamesenseDrillEngine({ config, onComplete }: Props) {
  const [idx,     setIdx]     = useState(0);
  const [results, setResults] = useState<{ correct: boolean; label: string }[]>([]);
  const [done,    setDone]    = useState(false);

  const scenarios = config.scenarios;

  const handleAnswer = useCallback((correct: boolean, label: string) => {
    const next = [...results, { correct, label }];
    setResults(next);

    setTimeout(() => {
      if (idx + 1 >= scenarios.length) {
        setDone(true);
        const correctCount = next.filter(r => r.correct).length;
        onComplete({
          correct: correctCount,
          total:   scenarios.length,
          score:   Math.round(correctCount / scenarios.length * 100),
        });
      } else {
        setIdx(i => i + 1);
      }
    }, 1800);
  }, [idx, results, scenarios.length, onComplete]);

  if (done) {
    const correctCount = results.filter(r => r.correct).length;
    const score = Math.round(correctCount / scenarios.length * 100);
    return (
      <div className="gs-done">
        <span className="label">Gamesense drill complete</span>
        <h2>Result</h2>
        <div className="gs-done__stats">
          <div className="gs-done__stat">
            <span className="mono" style={{ color: 'var(--teal)' }}>{correctCount}</span>
            <span className="label">Correct</span>
          </div>
          <div className="gs-done__stat">
            <span className="mono" style={{ color: 'var(--red)' }}>{scenarios.length - correctCount}</span>
            <span className="label">Wrong</span>
          </div>
          <div className="gs-done__stat">
            <span className="mono" style={{ color: score >= 60 ? 'var(--teal)' : 'var(--red)' }}>
              {score}%
            </span>
            <span className="label">Score</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="gs-engine">
      <ScenarioView
        key={idx}
        scenario={scenarios[idx]}
        index={idx}
        total={scenarios.length}
        onAnswer={handleAnswer}
      />
    </div>
  );
}
