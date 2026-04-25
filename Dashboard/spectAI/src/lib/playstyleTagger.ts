// src/lib/playstyleTagger.ts
// Derives playstyle tags and skill scores from tracker.gg data.
// No external LLM call needed at profile load — pure heuristic tagging.
// For richer AI summaries, wire this to the FetchAI agent layer.

import type { ParsedTrackerData } from '@/types/tracker';
import type { PlaystyleTag } from '@/types/player';

interface PlaystyleResult {
  tags: PlaystyleTag[];
  desc: string;
  aim_score:       number;
  gamesense_score: number;
  mechanics_score: number;
  util_score:      number;
  igl_score:       number;
}

// Normalize a value between known min/max to 0–100
function normalize(value: number, min: number, max: number): number {
  return Math.round(Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100)));
}

export function tagPlaystyle(data: ParsedTrackerData): PlaystyleResult {
  const { kd_ratio, headshot_pct, win_rate, avg_score, avg_damage, clutch_pct, agent_prefs } = data;

  const tags: PlaystyleTag[] = [];

  // ── Role-based tags from agent preferences ───────────────
  const primaryRole = agent_prefs[0]?.role;
  if (primaryRole === 'Duelist')    tags.push('Entry Fragger');
  if (primaryRole === 'Controller') tags.push('Support');
  if (primaryRole === 'Sentinel')   tags.push('Anchor');
  if (primaryRole === 'Initiator')  tags.push('Support');

  // ── Performance-based tags ────────────────────────────────
  if (kd_ratio >= 1.5)   tags.push('Aggressive');
  if (kd_ratio <= 0.85)  tags.push('Passive');

  if (clutch_pct >= 35)  tags.push('Clutch King');
  if (win_rate >= 55 && avg_score >= 220) tags.push('IGL');

  // lurker: good KD but below-avg first bloods → fights off-angle
  if (kd_ratio >= 1.2 && avg_damage < 160) tags.push('Lurker');

  // check agent variety — flex player
  const uniqueRoles = new Set(agent_prefs.map(a => a.role));
  if (uniqueRoles.size >= 3) tags.push('Flex');

  // De-dup and cap at 4 tags
  const uniqueTags = [...new Set(tags)].slice(0, 4) as PlaystyleTag[];

  // ── Skill scores ────────────────────────────────────────
  const aim_score       = normalize(headshot_pct, 10, 40);        // 10%–40% HS range
  const gamesense_score = normalize(win_rate, 35, 70);            // 35%–70% WR range
  const mechanics_score = normalize(avg_score, 130, 320);         // ACS range
  const util_score      = normalize(avg_damage - kd_ratio * 100, 20, 120); // util dmg proxy
  const igl_score       = normalize(win_rate * kd_ratio, 30, 90);

  // ── Short description ─────────────────────────────────────
  const rankLabel = data.current_rank;
  const topAgent  = agent_prefs[0]?.name ?? 'Unknown';
  const desc = buildDesc(uniqueTags, rankLabel, topAgent, kd_ratio, headshot_pct, win_rate);

  return { tags: uniqueTags, desc, aim_score, gamesense_score, mechanics_score, util_score, igl_score };
}

function buildDesc(
  tags: PlaystyleTag[],
  rank: string,
  topAgent: string,
  kd: number,
  hs: number,
  wr: number
): string {
  const tagStr = tags.length ? tags.join(', ') : 'Adaptive';
  const aimAdj = hs >= 28 ? 'precise' : hs >= 18 ? 'consistent' : 'developing';
  const wrAdj  = wr >= 55 ? 'strong' : wr >= 45 ? 'balanced' : 'improving';
  return (
    `${rank} player maining ${topAgent}. Playstyle: ${tagStr}. ` +
    `${aimAdj.charAt(0).toUpperCase() + aimAdj.slice(1)} aim (${hs.toFixed(1)}% HS), ` +
    `${wrAdj} win rate (${wr.toFixed(1)}%), KD ${kd.toFixed(2)}.`
  );
}
