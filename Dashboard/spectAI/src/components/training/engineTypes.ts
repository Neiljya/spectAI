// src/components/training/engineTypes.ts

export type ArenaPresetId =
  | 'jiggle_peek_lane'
  | 'jump_peek_info_lane'
  | 'angle_clear_house'
  | 'crossfire_clear'
  | 'postplant_box_site'
  | 'entry_smoke_lane'
  | 'default_range';

export interface AimDrillTask {
  kind: 'aim_script' | 'scenario_script';

  // New generic map system.
  arena_preset?: ArenaPresetId | string;

  // Keep this only for old DB tasks/backward compatibility.
  map_theme?: string;

  drill_name: string;
  drill_instructions: string;
  drill_script: string;
}

export interface GamesenseOption {
  label: string;
  is_correct: boolean;
  reasoning: string;
}

export interface GamesenseScenario {
  situation: string;
  map?: string;
  technique?: string;
  round_type: string;
  your_role: string;
  intel: string[];
  options: GamesenseOption[];
  time_limit_seconds: number;
}

export interface GamesenseConfig {
  kind: 'gamesense';
  scenarios: GamesenseScenario[];
}