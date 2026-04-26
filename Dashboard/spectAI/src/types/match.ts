// src/types/match.ts
// ============================================================
// MODULAR MATCH SCHEMA
// To add/remove/rename a field:
//   1. Edit MATCH_SCHEMA below only.
//   2. Bump CURRENT_SCHEMA_VERSION.
//   3. The upload form, validation, and display auto-update.
//   4. Supabase: no migration needed — data column is JSONB.
// ============================================================

export type FieldType = 'number' | 'string' | 'boolean' | 'select';

export interface MatchField {
  key: string;                  // JSONB key — must be unique
  label: string;                // Display label
  type: FieldType;
  group: string;                // Groups fields into sections in the UI
  required?: boolean;
  min?: number;
  max?: number;
  options?: string[];           // For select fields
  placeholder?: string;
  description?: string;         // Shown as tooltip
}

// ----------------------------------------------------------
// CURRENT SCHEMA VERSION
// Bump this whenever you add/remove fields.
// Old match rows keep their original schema_version.
// ----------------------------------------------------------
export const CURRENT_SCHEMA_VERSION = 1;

// ----------------------------------------------------------
// THE SCHEMA REGISTRY
// This is the single source of truth for match data fields.
// ----------------------------------------------------------
export const MATCH_SCHEMA: MatchField[] = [
  // ── Core ──────────────────────────────────────────────
  {
    key: 'map', label: 'Map', type: 'select', group: 'core', required: true,
    options: ['Ascent','Bind','Breeze','Fracture','Haven','Icebox','Lotus','Pearl','Split','Sunset'],
  },
  {
    key: 'agent', label: 'Agent', type: 'string', group: 'core', required: true,
    placeholder: 'e.g. Jett',
  },
  {
    key: 'outcome', label: 'Outcome', type: 'select', group: 'core', required: true,
    options: ['Win', 'Loss', 'Draw'],
  },
  {
    key: 'mode', label: 'Game Mode', type: 'select', group: 'core',
    options: ['Competitive', 'Unrated', 'Spike Rush', 'Deathmatch', 'Escalation', 'Custom'],
  },
  {
    key: 'score_us', label: 'Our Score', type: 'number', group: 'core',
    required: true, min: 0, max: 25,
  },
  {
    key: 'score_them', label: 'Their Score', type: 'number', group: 'core',
    required: true, min: 0, max: 25,
  },

  // ── Combat ────────────────────────────────────────────
  { key: 'kills',   label: 'Kills',   type: 'number', group: 'combat', required: true, min: 0, max: 60 },
  { key: 'deaths',  label: 'Deaths',  type: 'number', group: 'combat', required: true, min: 0, max: 60 },
  { key: 'assists', label: 'Assists', type: 'number', group: 'combat', min: 0, max: 60 },
  { key: 'score',   label: 'Combat Score (ACS)', type: 'number', group: 'combat', min: 0, max: 600 },
  { key: 'damage',  label: 'Total Damage', type: 'number', group: 'combat', min: 0 },
  { key: 'headshot_pct', label: 'Headshot %', type: 'number', group: 'combat', min: 0, max: 100,
    description: 'Percentage of shots that hit the head' },
  { key: 'first_bloods', label: 'First Bloods', type: 'number', group: 'combat', min: 0, max: 25 },
  { key: 'clutches', label: 'Clutches Won', type: 'number', group: 'combat', min: 0 },

  // ── Economy ───────────────────────────────────────────
  { key: 'avg_economy', label: 'Avg Economy', type: 'number', group: 'economy', min: 0,
    description: 'Average credits spent per round' },
  { key: 'plants', label: 'Spike Plants', type: 'number', group: 'economy', min: 0, max: 25 },
  { key: 'defuses', label: 'Spike Defuses', type: 'number', group: 'economy', min: 0, max: 25 },

  // ── Utility ───────────────────────────────────────────
  { key: 'util_usage',   label: 'Utility Used',   type: 'number', group: 'utility', min: 0,
    description: 'Number of utility casts this match' },
  { key: 'util_damage',  label: 'Utility Damage', type: 'number', group: 'utility', min: 0 },
  { key: 'flash_assists', label: 'Flash Assists', type: 'number', group: 'utility', min: 0 },

  // ── Notes ─────────────────────────────────────────────
  { key: 'notes', label: 'Match Notes', type: 'string', group: 'notes',
    placeholder: 'Any observations, tilts, good/bad decisions...' },
];

// ----------------------------------------------------------
// GROUPED SCHEMA (used by form and display components)
// ----------------------------------------------------------
export const MATCH_SCHEMA_GROUPS = MATCH_SCHEMA.reduce<Record<string, MatchField[]>>((acc, field) => {
  if (!acc[field.group]) acc[field.group] = [];
  acc[field.group].push(field);
  return acc;
}, {});

export const GROUP_LABELS: Record<string, string> = {
  core:     'Match Info',
  combat:   'Combat Stats',
  economy:  'Economy',
  utility:  'Utility',
  notes:    'Notes',
};

// ----------------------------------------------------------
// Row shape stored in Supabase
// ----------------------------------------------------------
export type MatchDataPayload = Record<string, string | number | boolean | null>;

export interface MatchRow {
  id: string;
  profile_id: string;
  match_id: string | null;
  played_at: string;
  uploaded_at: string;
  schema_version: number;
  data: MatchDataPayload;
  coach_notes: {
    summary?: string;
    key_moments?: string[];
    decisions?: string[];
  };
  training_plan: {
    drills?: { name: string; description: string; duration_min: number; resource_url?: string }[];
    focus_areas?: string[];
  };
  map: string | null;
  agent: string | null;
  outcome: string | null;
  
  attachments: string[];             // Array of image URLs (max 5)
  performance_summary: string | null; // AI or User summary of the match
}
