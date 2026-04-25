// src/types/tracker.ts

export interface TrackerSegment {
  type: string;
  attributes: Record<string, string>;
  metadata: {
    name?: string;
    imageUrl?: string;
    tierName?: string;
    color?: string;
    [key: string]: unknown;
  };
  stats: Record<string, {
    rank: number | null;
    percentile: number | null;
    displayName: string;
    displayCategory: string;
    value: number;
    displayValue: string;
    [key: string]: unknown;
  }>;
}

export interface TrackerResponse {
  data: {
    platformInfo: {
      platformUserIdentifier: string;
      avatarUrl: string;
    };
    segments: TrackerSegment[];
    metadata: {
      currentSeason: string;
    };
  };
}

export interface ParsedTrackerData {
  riot_id: string;
  avatar_url: string;
  current_rank: string;
  rank_tier: number;
  peak_rank: string;
  rr: number;
  kd_ratio: number;
  headshot_pct: number;
  win_rate: number;
  avg_score: number;
  avg_damage: number;
  avg_kills: number;
  avg_deaths: number;
  avg_assists: number;
  aces: number;
  clutch_pct: number;
  agent_prefs: {
    name: string;
    role: string;
    win_rate: number;
    kd: number;
    hours: number;
  }[];
  raw: unknown;
}
