// src/types/player.ts

export interface Profile {
  id: string;
  username: string;
  riot_id: string | null;
  riot_puuid: string | null;
  avatar_url: string | null;
  region: string;
  created_at: string;
  updated_at: string;
}

export interface AgentPref {
  name: string;
  role: 'Duelist' | 'Controller' | 'Initiator' | 'Sentinel';
  win_rate: number;
  kd: number;
  hours: number;
}

export type PlaystyleTag =
  | 'Entry Fragger'
  | 'Lurker'
  | 'Support'
  | 'IGL'
  | 'Anchor'
  | 'Flex'
  | 'Passive'
  | 'Aggressive'
  | 'Clutch King'
  | 'Space Taker';

export interface PlayerStats {
  id: string;
  profile_id: string;
  synced_at: string;

  current_rank: string | null;
  rank_tier: number | null;
  peak_rank: string | null;
  rr: number | null;

  kd_ratio: number | null;
  headshot_pct: number | null;
  win_rate: number | null;
  avg_score: number | null;
  avg_damage: number | null;
  avg_kills: number | null;
  avg_deaths: number | null;
  avg_assists: number | null;
  aces: number;
  clutch_pct: number | null;

  agent_prefs: AgentPref[];
  playstyle_tags: PlaystyleTag[];
  playstyle_desc: string | null;

  aim_score: number | null;
  gamesense_score: number | null;
  mechanics_score: number | null;
  util_score: number | null;
  igl_score: number | null;

  raw_tracker_data: Record<string, unknown> | null;
}
