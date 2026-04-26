// src/components/training/arenas/arenaPresets.ts

export type Vec3 = [number, number, number];

export interface ArenaWall {
  id: string;
  position: Vec3;
  scale: Vec3;
  color?: string;
}

export interface ArenaCover {
  id: string;
  position: Vec3;
  scale: Vec3;
  color?: string;
}

export interface ArenaPoint {
  id: string;
  label: string;
  position: Vec3;
}

export interface ArenaPreset {
  id: string;
  label: string;
  description: string;
  floorSize: Vec3;
  spawn: Vec3;
  walls: ArenaWall[];
  cover: ArenaCover[];
  points: Record<string, ArenaPoint>;
}

const WALL = '#30343f';
const COVER = '#555b66';

export const ARENA_PRESETS: Record<string, ArenaPreset> = {
  default_range: {
    id: 'default_range',
    label: 'Default Range',
    description: 'Open range for fallback drills.',
    floorSize: [80, 1, 80],
    spawn: [0, 1.6, 0],
    walls: [
      {
        id: 'back_wall',
        position: [0, 3, -45],
        scale: [80, 6, 1],
        color: WALL,
      },
      {
        id: 'left_wall',
        position: [-40, 3, -20],
        scale: [1, 6, 50],
        color: WALL,
      },
      {
        id: 'right_wall',
        position: [40, 3, -20],
        scale: [1, 6, 50],
        color: WALL,
      },
    ],
    cover: [],
    points: {
      player_start: {
        id: 'player_start',
        label: 'Player Start',
        position: [0, 1.6, 0],
      },
      mid_enemy: {
        id: 'mid_enemy',
        label: 'Mid Enemy',
        position: [0, 0, -18],
      },
      first_contact: {
        id: 'first_contact',
        label: 'First Contact',
        position: [0, 0, -18],
      },
      wide_swing: {
        id: 'wide_swing',
        label: 'Wide Swing',
        position: [8, 0, -18],
      },
      far_enemy: {
        id: 'far_enemy',
        label: 'Far Enemy',
        position: [0, 0, -32],
      },
      left_enemy: {
        id: 'left_enemy',
        label: 'Left Enemy',
        position: [-8, 0, -20],
      },
      right_enemy: {
        id: 'right_enemy',
        label: 'Right Enemy',
        position: [8, 0, -20],
      },
      utility_landing: {
        id: 'utility_landing',
        label: 'Utility Landing',
        position: [0, 1, -16],
      },
    },
  },

  jiggle_peek_lane: {
    id: 'jiggle_peek_lane',
    label: 'Jiggle Peek Lane',
    description:
      'A narrow angle with a corner for shoulder peeking and baiting shots.',
    floorSize: [70, 1, 70],
    spawn: [0, 1.6, 0],
    walls: [
      {
        id: 'left_boundary',
        position: [-18, 3, -22],
        scale: [1, 6, 46],
        color: WALL,
      },
      {
        id: 'right_boundary',
        position: [18, 3, -22],
        scale: [1, 6, 46],
        color: WALL,
      },
      {
        id: 'back_boundary',
        position: [0, 3, -46],
        scale: [36, 6, 1],
        color: WALL,
      },
      {
        id: 'corner_wall_main',
        position: [-4, 3, -12],
        scale: [8, 6, 1.2],
        color: WALL,
      },
      {
        id: 'corner_wall_side',
        position: [-8, 3, -8],
        scale: [1.2, 6, 8],
        color: WALL,
      },
    ],
    cover: [
      {
        id: 'enemy_head_box',
        position: [6, 1.1, -25],
        scale: [2.5, 2.2, 1.4],
        color: COVER,
      },
    ],
    points: {
      player_start: {
        id: 'player_start',
        label: 'Player Start',
        position: [0, 1.6, 0],
      },
      peek_corner: {
        id: 'peek_corner',
        label: 'Peek Corner',
        position: [-6.6, 1.6, -8],
      },
      safe_side: {
        id: 'safe_side',
        label: 'Safe Side',
        position: [-10, 1.6, -8],
      },
      exposed_side: {
        id: 'exposed_side',
        label: 'Exposed Side',
        position: [-4, 1.6, -8],
      },
      first_contact: {
        id: 'first_contact',
        label: 'First Contact',
        position: [6, 0, -24],
      },
      deep_angle: {
        id: 'deep_angle',
        label: 'Deep Angle',
        position: [10, 0, -33],
      },
      wide_swing: {
        id: 'wide_swing',
        label: 'Wide Swing Enemy',
        position: [12, 0, -18],
      },
      utility_landing: {
        id: 'utility_landing',
        label: 'Utility Landing',
        position: [-3, 1, -14],
      },
    },
  },

  jump_peek_info_lane: {
    id: 'jump_peek_info_lane',
    label: 'Jump Peek Info Lane',
    description: 'A long lane for gathering info without committing to a fight.',
    floorSize: [80, 1, 90],
    spawn: [0, 1.6, 0],
    walls: [
      {
        id: 'left_boundary',
        position: [-20, 3, -26],
        scale: [1, 6, 58],
        color: WALL,
      },
      {
        id: 'right_boundary',
        position: [20, 3, -26],
        scale: [1, 6, 58],
        color: WALL,
      },
      {
        id: 'back_boundary',
        position: [0, 3, -56],
        scale: [40, 6, 1],
        color: WALL,
      },
      {
        id: 'info_corner_a',
        position: [-5, 3, -12],
        scale: [10, 6, 1],
        color: WALL,
      },
      {
        id: 'info_corner_b',
        position: [-10, 3, -7],
        scale: [1, 6, 10],
        color: WALL,
      },
    ],
    cover: [
      {
        id: 'long_cover',
        position: [5, 1.2, -34],
        scale: [3, 2.4, 1.6],
        color: COVER,
      },
      {
        id: 'deep_cover',
        position: [-6, 1.2, -44],
        scale: [3, 2.4, 1.6],
        color: COVER,
      },
    ],
    points: {
      player_start: {
        id: 'player_start',
        label: 'Player Start',
        position: [0, 1.6, 0],
      },
      jump_peek_corner: {
        id: 'jump_peek_corner',
        label: 'Jump Peek Corner',
        position: [-8, 1.6, -8],
      },
      info_lane_mid: {
        id: 'info_lane_mid',
        label: 'Mid Info',
        position: [4, 0, -32],
      },
      info_lane_deep: {
        id: 'info_lane_deep',
        label: 'Deep Info',
        position: [-6, 0, -45],
      },
      operator_angle: {
        id: 'operator_angle',
        label: 'Operator Angle',
        position: [8, 0, -50],
      },
      fallback: {
        id: 'fallback',
        label: 'Fallback',
        position: [-12, 1.6, -5],
      },
      utility_landing: {
        id: 'utility_landing',
        label: 'Utility Landing',
        position: [0, 1, -28],
      },
    },
  },

  angle_clear_house: {
    id: 'angle_clear_house',
    label: 'Angle Clear House',
    description:
      'Doorway-style angle clearing arena with true left/right blind pockets.',
    floorSize: [80, 1, 85],
    spawn: [0, 1.6, 2],
    walls: [
      {
        id: 'back_boundary',
        position: [0, 3, -54],
        scale: [52, 6, 1],
        color: WALL,
      },
      {
        id: 'left_boundary',
        position: [-26, 3, -27],
        scale: [1, 6, 54],
        color: WALL,
      },
      {
        id: 'right_boundary',
        position: [26, 3, -27],
        scale: [1, 6, 54],
        color: WALL,
      },

      {
        id: 'entry_left_wall',
        position: [-14.5, 3, -14],
        scale: [23, 6, 1.2],
        color: WALL,
      },
      {
        id: 'entry_right_wall',
        position: [14.5, 3, -14],
        scale: [23, 6, 1.2],
        color: WALL,
      },

      {
        id: 'left_pocket_side',
        position: [-17, 3, -23],
        scale: [1.2, 6, 16],
        color: WALL,
      },
      {
        id: 'left_pocket_back',
        position: [-11, 3, -31],
        scale: [12, 6, 1.2],
        color: WALL,
      },

      {
        id: 'right_pocket_side',
        position: [17, 3, -23],
        scale: [1.2, 6, 16],
        color: WALL,
      },
      {
        id: 'right_pocket_back',
        position: [11, 3, -31],
        scale: [12, 6, 1.2],
        color: WALL,
      },

      {
        id: 'deep_center_block',
        position: [0, 3, -36],
        scale: [6, 6, 9],
        color: WALL,
      },
    ],
    cover: [
      {
        id: 'left_box',
        position: [-9, 1.2, -38],
        scale: [3, 2.4, 2],
        color: COVER,
      },
      {
        id: 'right_box',
        position: [9, 1.2, -38],
        scale: [3, 2.4, 2],
        color: COVER,
      },
    ],
    points: {
      player_start: {
        id: 'player_start',
        label: 'Player Start',
        position: [0, 1.6, 2],
      },

      slice_entry: {
        id: 'slice_entry',
        label: 'Slice Entry',
        position: [0, 1.6, -10],
      },
      left_slice: {
        id: 'left_slice',
        label: 'Left Slice Position',
        position: [-3.4, 1.6, -13],
      },
      right_slice: {
        id: 'right_slice',
        label: 'Right Slice Position',
        position: [3.4, 1.6, -13],
      },
      deep_slice: {
        id: 'deep_slice',
        label: 'Deep Slice Position',
        position: [0, 1.6, -24],
      },

      left_pocket: {
        id: 'left_pocket',
        label: 'Left Blind Pocket',
        position: [-10.5, 0, -21],
      },
      right_pocket: {
        id: 'right_pocket',
        label: 'Right Blind Pocket',
        position: [10.5, 0, -21],
      },

      close_left: {
        id: 'close_left',
        label: 'Close Left',
        position: [-10.5, 0, -21],
      },
      close_right: {
        id: 'close_right',
        label: 'Close Right',
        position: [10.5, 0, -21],
      },
      first_left: {
        id: 'first_left',
        label: 'First Left',
        position: [-10.5, 0, -21],
      },
      first_right: {
        id: 'first_right',
        label: 'First Right',
        position: [10.5, 0, -21],
      },

      deep_left: {
        id: 'deep_left',
        label: 'Deep Left',
        position: [-13.5, 0, -41],
      },
      deep_right: {
        id: 'deep_right',
        label: 'Deep Right',
        position: [13.5, 0, -41],
      },
      center_clear: {
        id: 'center_clear',
        label: 'Center Clear',
        position: [0, 0, -47],
      },

      utility_landing: {
        id: 'utility_landing',
        label: 'Utility Landing',
        position: [0, 1, -24],
      },
    },
  },

  crossfire_clear: {
    id: 'crossfire_clear',
    label: 'Crossfire Clear',
    description:
      'Two-angle pressure for isolating fights and avoiding dry wide swings.',
    floorSize: [80, 1, 80],
    spawn: [0, 1.6, 0],
    walls: [
      {
        id: 'left_boundary',
        position: [-22, 3, -24],
        scale: [1, 6, 52],
        color: WALL,
      },
      {
        id: 'right_boundary',
        position: [22, 3, -24],
        scale: [1, 6, 52],
        color: WALL,
      },
      {
        id: 'back_boundary',
        position: [0, 3, -50],
        scale: [44, 6, 1],
        color: WALL,
      },
      {
        id: 'center_cover_wall',
        position: [0, 3, -26],
        scale: [5, 6, 8],
        color: WALL,
      },
    ],
    cover: [
      {
        id: 'left_cover',
        position: [-9, 1.2, -28],
        scale: [3, 2.4, 2],
        color: COVER,
      },
      {
        id: 'right_cover',
        position: [9, 1.2, -28],
        scale: [3, 2.4, 2],
        color: COVER,
      },
    ],
    points: {
      player_start: {
        id: 'player_start',
        label: 'Player Start',
        position: [0, 1.6, 0],
      },
      isolate_left: {
        id: 'isolate_left',
        label: 'Isolate Left',
        position: [-7, 1.6, -18],
      },
      isolate_right: {
        id: 'isolate_right',
        label: 'Isolate Right',
        position: [7, 1.6, -18],
      },
      left_crossfire: {
        id: 'left_crossfire',
        label: 'Left Crossfire',
        position: [-12, 0, -32],
      },
      right_crossfire: {
        id: 'right_crossfire',
        label: 'Right Crossfire',
        position: [12, 0, -32],
      },
      deep_anchor: {
        id: 'deep_anchor',
        label: 'Deep Anchor',
        position: [0, 0, -42],
      },
      utility_landing: {
        id: 'utility_landing',
        label: 'Utility Landing',
        position: [0, 1, -25],
      },
    },
  },

  postplant_box_site: {
    id: 'postplant_box_site',
    label: 'Post-Plant Box Site',
    description:
      'Generic post-plant site with default plant, cover, tap cue, and swing timing.',
    floorSize: [80, 1, 80],
    spawn: [0, 1.6, 0],
    walls: [
      {
        id: 'back_boundary',
        position: [0, 3, -48],
        scale: [44, 6, 1],
        color: WALL,
      },
      {
        id: 'left_boundary',
        position: [-22, 3, -24],
        scale: [1, 6, 52],
        color: WALL,
      },
      {
        id: 'right_boundary',
        position: [22, 3, -24],
        scale: [1, 6, 52],
        color: WALL,
      },
    ],
    cover: [
      {
        id: 'default_box',
        position: [0, 1.25, -30],
        scale: [5, 2.5, 3],
        color: COVER,
      },
      {
        id: 'left_box',
        position: [-10, 1.2, -24],
        scale: [3, 2.4, 2],
        color: COVER,
      },
      {
        id: 'right_box',
        position: [10, 1.2, -36],
        scale: [3, 2.4, 2],
        color: COVER,
      },
    ],
    points: {
      player_start: {
        id: 'player_start',
        label: 'Player Start',
        position: [0, 1.6, 0],
      },
      default_plant: {
        id: 'default_plant',
        label: 'Default Plant',
        position: [0, 0.05, -31],
      },
      tap_enemy: {
        id: 'tap_enemy',
        label: 'Tap Enemy',
        position: [4, 0, -34],
      },
      left_retaker: {
        id: 'left_retaker',
        label: 'Left Retaker',
        position: [-12, 0, -25],
      },
      right_retaker: {
        id: 'right_retaker',
        label: 'Right Retaker',
        position: [12, 0, -36],
      },
      safe_postplant: {
        id: 'safe_postplant',
        label: 'Safe Postplant',
        position: [-8, 1.6, -18],
      },
      swing_timing: {
        id: 'swing_timing',
        label: 'Swing Timing',
        position: [3, 1.6, -24],
      },
      utility_landing: {
        id: 'utility_landing',
        label: 'Utility Landing',
        position: [0, 1, -30],
      },
    },
  },

  entry_smoke_lane: {
    id: 'entry_smoke_lane',
    label: 'Entry Lane',
    description: 'Entry lane for timing, first-fight control, and space taking.',
    floorSize: [80, 1, 90],
    spawn: [0, 1.6, 0],
    walls: [
      {
        id: 'left_boundary',
        position: [-22, 3, -28],
        scale: [1, 6, 60],
        color: WALL,
      },
      {
        id: 'right_boundary',
        position: [22, 3, -28],
        scale: [1, 6, 60],
        color: WALL,
      },
      {
        id: 'back_boundary',
        position: [0, 3, -58],
        scale: [44, 6, 1],
        color: WALL,
      },
      {
        id: 'entry_choke_left',
        position: [-7, 3, -16],
        scale: [1, 6, 12],
        color: WALL,
      },
      {
        id: 'entry_choke_right',
        position: [7, 3, -16],
        scale: [1, 6, 12],
        color: WALL,
      },
    ],
    cover: [
      {
        id: 'site_box_left',
        position: [-8, 1.2, -36],
        scale: [3, 2.4, 2],
        color: COVER,
      },
      {
        id: 'site_box_right',
        position: [8, 1.2, -36],
        scale: [3, 2.4, 2],
        color: COVER,
      },
    ],
    points: {
      player_start: {
        id: 'player_start',
        label: 'Player Start',
        position: [0, 1.6, 0],
      },
      choke: {
        id: 'choke',
        label: 'Choke',
        position: [0, 1.6, -14],
      },
      smoke_landing: {
        id: 'smoke_landing',
        label: 'Smoke Landing',
        position: [0, 1, -24],
      },
      dash_exit: {
        id: 'dash_exit',
        label: 'Entry Exit',
        position: [0, 1.6, -28],
      },
      close_left: {
        id: 'close_left',
        label: 'Close Left',
        position: [-9, 0, -25],
      },
      close_right: {
        id: 'close_right',
        label: 'Close Right',
        position: [9, 0, -25],
      },
      site_left: {
        id: 'site_left',
        label: 'Site Left',
        position: [-10, 0, -38],
      },
      site_right: {
        id: 'site_right',
        label: 'Site Right',
        position: [10, 0, -38],
      },
      deep_site: {
        id: 'deep_site',
        label: 'Deep Site',
        position: [0, 0, -48],
      },
      first_contact: {
        id: 'first_contact',
        label: 'First Contact',
        position: [-9, 0, -25],
      },
      wide_swing: {
        id: 'wide_swing',
        label: 'Wide Swing',
        position: [9, 0, -25],
      },
      utility_landing: {
        id: 'utility_landing',
        label: 'Utility Landing',
        position: [0, 1, -24],
      },
    },
  },
};

export function getArenaPreset(id?: string): ArenaPreset {
  return ARENA_PRESETS[id ?? 'default_range'] ?? ARENA_PRESETS.default_range;
}

export function resolveArenaPoint(
  arenaId: string | undefined,
  pointId: string,
  fallback: Vec3 = [0, 1.6, -15]
): Vec3 {
  const arena = getArenaPreset(arenaId);
  const clean = pointId.includes('.')
    ? pointId.split('.').pop() ?? pointId
    : pointId;

  return arena.points[clean]?.position ?? fallback;
}

export function getPromptArenaPresets() {
  return Object.values(ARENA_PRESETS).map(arena => ({
    id: arena.id,
    label: arena.label,
    description: arena.description,
    points: Object.values(arena.points).map(point => ({
      id: point.id,
      label: point.label,
      position: point.position,
    })),
  }));
}