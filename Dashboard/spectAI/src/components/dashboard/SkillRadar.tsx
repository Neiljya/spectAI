// src/components/dashboard/SkillRadar.tsx
import type { PlayerStats } from '../../types/player';
import './SkillRadar.css';

interface Props { stats: PlayerStats; }

const AXES = [
  { key: 'aim_score',       label: 'Aim' },
  { key: 'gamesense_score', label: 'Game Sense' },
  { key: 'mechanics_score', label: 'Mechanics' },
  { key: 'util_score',      label: 'Utility' },
  { key: 'igl_score',       label: 'IGL' },
] as const;

const SIZE   = 220;
const CX     = SIZE / 2;
const CY     = SIZE / 2;
const RINGS  = [0.25, 0.5, 0.75, 1.0];
const N      = AXES.length;

function polar(angle: number, r: number): [number, number] {
  const rad = (angle - 90) * (Math.PI / 180);
  return [CX + r * Math.cos(rad), CY + r * Math.sin(rad)];
}

function polygon(values: number[], maxR: number): string {
  return values
    .map((v, i) => {
      const [x, y] = polar((360 / N) * i, (v / 100) * maxR);
      return `${x},${y}`;
    })
    .join(' ');
}

export function SkillRadar({ stats }: Props) {
  const scores = AXES.map(a => (stats[a.key] ?? 0) as number);
  const maxR   = SIZE * 0.38;
  const labelR = SIZE * 0.50;

  return (
    <div className="skill-radar">
      <div className="skill-radar__header">
        <span className="label">Skill Profile</span>
        <span className="skill-radar__avg mono">
          {Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)}
          <span className="skill-radar__avg-label"> avg</span>
        </span>
      </div>

      <svg
        className="skill-radar__svg"
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        width="100%"
        aria-label="Skill radar chart"
      >
        {/* Grid rings */}
        {RINGS.map(ring => {
          const pts = Array.from({ length: N }, (_, i) => {
            const [x, y] = polar((360 / N) * i, maxR * ring);
            return `${x},${y}`;
          }).join(' ');
          return (
            <polygon
              key={ring}
              points={pts}
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="1"
            />
          );
        })}

        {/* Axis lines */}
        {AXES.map((_, i) => {
          const [x, y] = polar((360 / N) * i, maxR);
          return (
            <line
              key={i}
              x1={CX} y1={CY}
              x2={x}  y2={y}
              stroke="rgba(255,255,255,0.05)"
              strokeWidth="1"
            />
          );
        })}

        {/* Filled area */}
        <polygon
          points={polygon(scores, maxR)}
          fill="rgba(232,58,58,0.15)"
          stroke="rgba(232,58,58,0.7)"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />

        {/* Data points */}
        {scores.map((v, i) => {
          const [x, y] = polar((360 / N) * i, (v / 100) * maxR);
          return (
            <circle
              key={i}
              cx={x} cy={y}
              r="3"
              fill="var(--red)"
              stroke="var(--surface)"
              strokeWidth="1.5"
            />
          );
        })}

        {/* Labels */}
        {AXES.map((axis, i) => {
          const angle = (360 / N) * i;
          const [lx, ly] = polar(angle, labelR);
          const anchor =
            lx < CX - 4 ? 'end' :
            lx > CX + 4 ? 'start' : 'middle';
          const dy = ly < CY - 4 ? -6 : ly > CY + 4 ? 14 : 5;
          return (
            <text
              key={axis.key}
              x={lx}
              y={ly + dy}
              textAnchor={anchor}
              fontSize="9"
              fontFamily="'Share Tech Mono', monospace"
              letterSpacing="0.1em"
              textDecoration="uppercase"
              fill="rgba(140,149,160,0.9)"
            >
              {axis.label.toUpperCase()}
            </text>
          );
        })}

        {/* Score values near each point */}
        {scores.map((v, i) => {
          const angle = (360 / N) * i;
          const [vx, vy] = polar(angle, (v / 100) * maxR);
          const offX = vx < CX ? -10 : vx > CX ? 10 : 0;
          const offY = vy < CY ? -8  : vy > CY ? 14 : 5;
          return (
            <text
              key={`val-${i}`}
              x={vx + offX}
              y={vy + offY}
              textAnchor="middle"
              fontSize="8"
              fontFamily="'Share Tech Mono', monospace"
              fill="rgba(232,58,58,0.85)"
            >
              {v}
            </text>
          );
        })}
      </svg>

      {/* Legend row */}
      <div className="skill-radar__legend">
        {AXES.map((axis, i) => (
          <div className="skill-radar__item" key={axis.key}>
            <span className="skill-radar__item-label label">{axis.label}</span>
            <div className="skill-radar__item-bar">
              <div
                className="skill-radar__item-fill"
                style={{ width: `${scores[i]}%` }}
              />
            </div>
            <span className="skill-radar__item-score mono">{scores[i]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
