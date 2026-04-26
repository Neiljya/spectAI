// src/types/match.ts
// Matches the exact match_data table schema in Supabase

export type FieldType = 'number' | 'string' | 'boolean' | 'select';

export interface MatchField {
  key:         string;
  label:       string;
  type:        FieldType;
  group:       string;
  required?:   boolean;
  min?:        number;
  max?:        number;
  options?:    string[];
  placeholder?: string;
  description?: string;
}

export const CURRENT_SCHEMA_VERSION = 1;

export const MATCH_SCHEMA: MatchField[] = [
  // core
  { key: 'map',     label: 'Map',     type: 'select', group: 'core', required: true,
    options: ['Ascent','Bind','Breeze','Fracture','Haven','Icebox','Lotus','Pearl','Split','Sunset'] },
  { key: 'agent',   label: 'Agent',   type: 'string', group: 'core', required: true, placeholder: 'e.g. Jett' },
  { key: 'outcome', label: 'Outcome', type: 'select', group: 'core', required: true, options: ['Win','Loss','Draw'] },
  { key: 'mode',    label: 'Game Mode', type: 'select', group: 'core',
    options: ['Competitive','Unrated','Spike Rush','Deathmatch','Escalation','Custom'] },
  { key: 'score_us',   label: 'Our Score',   type: 'number', group: 'core', required: true, min: 0, max: 25 },
  { key: 'score_them', label: 'Their Score', type: 'number', group: 'core', required: true, min: 0, max: 25 },
  // combat
  { key: 'kills',   label: 'Kills',   type: 'number', group: 'combat', required: true, min: 0, max: 60 },
  { key: 'deaths',  label: 'Deaths',  type: 'number', group: 'combat', required: true, min: 0, max: 60 },
  { key: 'assists', label: 'Assists', type: 'number', group: 'combat', min: 0, max: 60 },
  { key: 'score',   label: 'ACS',     type: 'number', group: 'combat', min: 0, max: 600 },
  { key: 'damage',  label: 'Total Damage', type: 'number', group: 'combat', min: 0 },
  { key: 'headshot_pct', label: 'Headshot %', type: 'number', group: 'combat', min: 0, max: 100 },
  { key: 'first_bloods', label: 'First Bloods', type: 'number', group: 'combat', min: 0, max: 25 },
  { key: 'clutches',     label: 'Clutches Won', type: 'number', group: 'combat', min: 0 },
  // economy
  { key: 'avg_economy', label: 'Avg Economy', type: 'number', group: 'economy', min: 0 },
  { key: 'plants',      label: 'Spike Plants', type: 'number', group: 'economy', min: 0, max: 25 },
  { key: 'defuses',     label: 'Spike Defuses', type: 'number', group: 'economy', min: 0, max: 25 },
  // utility
  { key: 'util_usage',   label: 'Utility Used',   type: 'number', group: 'utility', min: 0 },
  { key: 'util_damage',  label: 'Utility Damage', type: 'number', group: 'utility', min: 0 },
  { key: 'flash_assists',label: 'Flash Assists',  type: 'number', group: 'utility', min: 0 },
  // notes
  { key: 'notes', label: 'Match Notes', type: 'string', group: 'notes', placeholder: 'Observations...' },
];

export const MATCH_SCHEMA_GROUPS = MATCH_SCHEMA.reduce<Record<string, MatchField[]>>((acc, f) => {
  if (!acc[f.group]) acc[f.group] = [];
  acc[f.group].push(f);
  return acc;
}, {});

export const GROUP_LABELS: Record<string, string> = {
  core:    'Match Info',
  combat:  'Combat Stats',
  economy: 'Economy',
  utility: 'Utility',
  notes:   'Notes',
};

export type MatchDataPayload = Record<string, string | number | boolean | null>;

// ── Matches the exact match_data table columns ─────────────
export interface MatchRow {
  id:                 string;
  profile_id:         string;
  match_id:           string | null;
  played_at:          string;
  uploaded_at:        string;
  schema_version:     number;

  // JSONB columns
  data:               MatchDataPayload;
  coach_notes:        CoachNotes | null;
  training_plan:      TrainingPlan | null;

  // Generated columns (stored text, derived from data->>'field')
  map:     string | null;
  agent:   string | null;
  outcome: string | null;

  // Plain text columns
  attachments:         string | null;   // text — comma-separated URLs or single URL
  performance_summary: string | null;   // text — free-form AI summary
}

export interface ClipNote {
  url:     string;
  comment: string;
}

export interface CoachNotes {
  summary?:    string;
  strengths?:  string[];
  weaknesses?: string[];
  clip_notes?: ClipNote[];
}

export interface TrainingPlan {
  drills?:      { name: string; description: string; duration_min: number; resource_url?: string }[];
  focus_areas?: string[];
}