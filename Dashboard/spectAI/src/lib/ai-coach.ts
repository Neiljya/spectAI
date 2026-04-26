// src/lib/ai-coach.ts
import { GoogleGenerativeAI } from '@google/generative-ai';
import { supabase } from './supabase';
import { getPromptArenaPresets } from '../components/training/arenas/arenaPresets';

const genAI = new GoogleGenerativeAI(
  import.meta.env.VITE_GEMINI_API_KEY as string
);

export type CoachMode = 'summary' | 'training';

export interface AIResponse {
  summary?: string;
  strengths?: string[];
  weaknesses?: string[];
  suggested_tasks?: unknown[];
}

type Difficulty = 'easy' | 'medium' | 'hard';

interface TemplateChoice {
  template_id: string;
  title?: string;
  description?: string;
  difficulty?: Difficulty;
  linked_weakness?: string;
  focus?: string;
}

interface TemplateDef {
  id: string;
  title: string;
  arena_preset: string;
  description: string;
  best_for: string[];
  script: (choice: TemplateChoice) => string;
}

const FORBIDDEN_SCRIPT_TOKENS = [
  'Drill.useAbility',
  'Drill.useAbilityAt',
  'Drill.bindAbility',
  'Drill.setArenaPreset',
  'Drill.loadArena',
  'Drill.changeArena',
  'Drill.setMap',
  'Drill.loadMap',
  '.isDead',
  '.health',
  '.hp',
  'getEnemy',
];

function extractJSON(text: string) {
  const cleaned = text
    .trim()
    .replace(/^```json/i, '')
    .replace(/^```/i, '')
    .replace(/```$/i, '')
    .trim();

  try {
    return JSON.parse(cleaned);
  } catch {
    const firstBrace = cleaned.indexOf('{');
    const lastBrace = cleaned.lastIndexOf('}');

    if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
      return JSON.parse(cleaned.slice(firstBrace, lastBrace + 1));
    }

    throw new Error('AI returned invalid JSON.');
  }
}

function difficulty(choice: TemplateChoice): Difficulty {
  if (choice.difficulty === 'easy') return 'easy';
  if (choice.difficulty === 'hard') return 'hard';
  return 'medium';
}

function timing(choice: TemplateChoice) {
  const d = difficulty(choice);

  if (d === 'easy') {
    return {
      cueMs: 950,
      swingSpeed: 4.5,
      timeoutMs: 18000,
      enemyReactionMs: 850,
    };
  }

  if (d === 'hard') {
    return {
      cueMs: 450,
      swingSpeed: 7.5,
      timeoutMs: 11000,
      enemyReactionMs: 450,
    };
  }

  return {
    cueMs: 650,
    swingSpeed: 6,
    timeoutMs: 14000,
    enemyReactionMs: 650,
  };
}

function safeTitle(choice: TemplateChoice, fallback: string) {
  return typeof choice.title === 'string' && choice.title.trim()
    ? choice.title.trim()
    : fallback;
}

function safeDescription(choice: TemplateChoice, fallback: string) {
  return typeof choice.description === 'string' && choice.description.trim()
    ? choice.description.trim()
    : fallback;
}

function safeWeakness(choice: TemplateChoice, fallback: string) {
  return typeof choice.linked_weakness === 'string' &&
    choice.linked_weakness.trim()
    ? choice.linked_weakness.trim()
    : fallback;
}

function scriptIsInvalid(script: string) {
  if (!script.trim()) return true;
  if (!script.includes('Drill.complete')) return true;
  return FORBIDDEN_SCRIPT_TOKENS.some(token => script.includes(token));
}

function fallbackScript(title: string) {
  return `
var score = 0;
var mistakes = 0;
var prepared = false;

Drill.setPlayerSpawn('player_start');

Drill.setObjective({
  title: ${JSON.stringify(title)},
  details: 'Set up the timing, wait for the cue, then punish the enemy movement.',
  requiredActions: ['setup', 'punish']
});

var enemy = Drill.spawnEnemyAt('first_contact', {
  behavior: 'hold_angle',
  label: 'angle holder',
  reactionMs: 650
});

Drill.addActionPrompt({
  id: 'setup',
  key: '1',
  label: 'Set up timing',
  hint: 'Use discipline before taking the fight',
  removeOnUse: false
});

Drill.addActionPrompt({
  id: 'punish',
  key: '2',
  label: 'Punish swing',
  hint: 'Use after the cue',
  removeOnUse: false
});

Drill.onAction('setup', function() {
  prepared = true;
  score += 1;
  Drill.markActionComplete('setup');

  Drill.emitCueAt('first_contact', {
    type: 'audio',
    message: 'Timing cue — enemy movement incoming',
    durationMs: 1200
  });

  Drill.after(650, function() {
    Drill.swingEnemy(enemy, Drill.resolvePoint('wide_swing'), 6);
  });

  Drill.setHUD({
    score: score,
    message: 'Setup complete. Punish the movement.'
  });
});

Drill.onAction('punish', function() {
  if (!prepared) {
    mistakes += 1;
    Drill.emitCue({
      type: 'danger',
      message: 'Too early — you committed without setup.',
      durationMs: 1200
    });
    return;
  }

  Drill.markActionComplete('punish');
  Drill.setHUD({
    score: score,
    message: 'Now click the enemy.'
  });
});

Drill.onEnemyHit(enemy, function() {
  score += 2;

  Drill.complete({
    score: score,
    message: mistakes === 0 ? 'Clean mechanics conversion.' : 'Completed, but your timing was sloppy.',
    passed: mistakes === 0
  });
});

Drill.after(12000, function() {
  Drill.complete({
    score: score,
    message: 'Too slow. You did not convert the setup into a clean punish.',
    passed: false
  });
});
`.trim();
}

const MECHANIC_TEMPLATES: TemplateDef[] = [
  {
    id: 'jiggle_peek',
    title: 'Jiggle Peek',
    arena_preset: 'jiggle_peek_lane',
    description:
      'Bait contact, avoid over-swinging, then punish the re-peek timing.',
    best_for: ['peek discipline', 'first contact', 'overheating', 'timing'],
    script(choice) {
      const t = timing(choice);
      const title = safeTitle(choice, 'Jiggle Peek');

      return `
var score = 0;
var mistakes = 0;
var baited = false;

Drill.setPlayerSpawn('player_start');

Drill.setObjective({
  title: ${JSON.stringify(title)},
  details: 'Bait the shot with a disciplined peek, then punish the enemy movement. Do not wide swing early.',
  requiredActions: ['bait_timing', 'punish_repeek']
});

var enemy = Drill.spawnEnemyAt('first_contact', {
  behavior: 'hold_angle',
  label: 'angle holder',
  reactionMs: ${t.enemyReactionMs}
});

Drill.addActionPrompt({
  id: 'bait_timing',
  key: '1',
  label: 'Bait timing',
  hint: 'Shoulder peek for info before committing',
  removeOnUse: false
});

Drill.addActionPrompt({
  id: 'punish_repeek',
  key: '2',
  label: 'Punish re-peek',
  hint: 'Use after the timing cue',
  removeOnUse: false
});

Drill.onAction('bait_timing', function() {
  baited = true;
  score += 1;
  Drill.markActionComplete('bait_timing');

  Drill.emitCueAt('first_contact', {
    type: 'audio',
    message: 'Shot baited — prepare for the re-peek',
    durationMs: 1200
  });

  Drill.after(${t.cueMs}, function() {
    Drill.swingEnemy(enemy, Drill.resolvePoint('wide_swing'), ${t.swingSpeed});
  });

  Drill.setHUD({
    score: score,
    message: 'Timing baited. Prepare to punish.'
  });
});

Drill.onAction('punish_repeek', function() {
  if (!baited) {
    mistakes += 1;
    Drill.emitCue({
      type: 'danger',
      message: 'Too early — you committed before baiting timing.',
      durationMs: 1200
    });
    return;
  }

  Drill.markActionComplete('punish_repeek');
  Drill.setHUD({
    score: score,
    message: 'Now click the swinging enemy.'
  });
});

Drill.onEnemyHit(enemy, function() {
  score += 2;

  Drill.complete({
    score: score,
    message: mistakes === 0 ? 'Clean jiggle peek conversion.' : 'Completed, but you committed too early.',
    passed: mistakes === 0
  });
});

Drill.after(${t.timeoutMs}, function() {
  Drill.complete({
    score: score,
    message: 'Too slow. You did not convert the timing window.',
    passed: false
  });
});
`.trim();
    },
  },

  {
    id: 'slicing_the_pie',
    title: 'Slicing the Pie',
    arena_preset: 'angle_clear_house',
    description:
      'Clear true left/right blind pockets one slice at a time instead of exposing yourself to every angle.',
    best_for: [
      'angle clearing',
      'crosshair placement',
      'discipline',
      'multi-angle fights',
    ],
    script(choice) {
      const t = timing(choice);
      const title = safeTitle(choice, 'Slicing the Pie');

      return `
var score = 0;
var mistakes = 0;
var leftCleared = false;
var rightCleared = false;
var deepCleared = false;

Drill.setPlayerSpawn('player_start');

Drill.setObjective({
  title: ${JSON.stringify(title)},
  details: 'Clear the doorway one slice at a time: left pocket, right pocket, then deep angle. Do not shoot deep before close pockets are cleared.',
  requiredActions: ['slice_left', 'slice_right', 'clear_deep']
});

Drill.createZoneAt('left_slice', {
  name: 'left_slice_zone',
  scale: [3, 1, 3],
  color: '#ffd166',
  visible: true,
  label: 'Left slice'
});

Drill.createZoneAt('right_slice', {
  name: 'right_slice_zone',
  scale: [3, 1, 3],
  color: '#ffd166',
  visible: true,
  label: 'Right slice'
});

Drill.createZoneAt('deep_slice', {
  name: 'deep_slice_zone',
  scale: [3, 1, 3],
  color: '#1dc8a0',
  visible: true,
  label: 'Deep clear'
});

var leftEnemy = Drill.spawnEnemyAt('left_pocket', {
  behavior: 'hold_angle',
  label: 'left blind pocket',
  reactionMs: ${t.enemyReactionMs}
});

var rightEnemy = Drill.spawnEnemyAt('right_pocket', {
  behavior: 'hold_angle',
  label: 'right blind pocket',
  reactionMs: ${t.enemyReactionMs}
});

var deepEnemy = Drill.spawnEnemyAt('deep_left', {
  behavior: 'hold_angle',
  label: 'deep angle',
  reactionMs: ${t.enemyReactionMs}
});

Drill.addActionPrompt({
  id: 'slice_left',
  key: '1',
  label: 'Slice left pocket',
  hint: 'Move to the left slice marker and isolate the blind pocket',
  removeOnUse: false
});

Drill.addActionPrompt({
  id: 'slice_right',
  key: '2',
  label: 'Slice right pocket',
  hint: 'Move to the right slice marker and isolate the blind pocket',
  removeOnUse: false
});

Drill.addActionPrompt({
  id: 'clear_deep',
  key: '3',
  label: 'Clear deep angle',
  hint: 'Only clear deep after both close pockets are handled',
  removeOnUse: false
});

Drill.onZoneEnter('left_slice_zone', function() {
  Drill.emitCueAt('left_pocket', {
    type: 'danger',
    message: 'Left pocket exposed',
    durationMs: 1000
  });

  Drill.swingEnemy(leftEnemy, Drill.resolvePoint('left_pocket'), ${t.swingSpeed});
});

Drill.onZoneEnter('right_slice_zone', function() {
  Drill.emitCueAt('right_pocket', {
    type: 'danger',
    message: 'Right pocket exposed',
    durationMs: 1000
  });

  Drill.swingEnemy(rightEnemy, Drill.resolvePoint('right_pocket'), ${t.swingSpeed});
});

Drill.onZoneEnter('deep_slice_zone', function() {
  if (!leftCleared || !rightCleared) {
    mistakes += 1;

    Drill.emitCue({
      type: 'danger',
      message: 'You exposed deep before clearing both close pockets.',
      durationMs: 1400
    });

    return;
  }

  Drill.emitCueAt('deep_left', {
    type: 'danger',
    message: 'Deep angle active',
    durationMs: 1000
  });

  Drill.swingEnemy(deepEnemy, Drill.resolvePoint('center_clear'), ${t.swingSpeed});
});

Drill.onAction('slice_left', function() {
  Drill.markActionComplete('slice_left');
  Drill.setHUD({
    score: score,
    message: 'Move to the left slice marker and clear only the left pocket.'
  });
});

Drill.onAction('slice_right', function() {
  Drill.markActionComplete('slice_right');
  Drill.setHUD({
    score: score,
    message: 'Move to the right slice marker and clear only the right pocket.'
  });
});

Drill.onAction('clear_deep', function() {
  Drill.markActionComplete('clear_deep');

  if (!leftCleared || !rightCleared) {
    mistakes += 1;
    Drill.emitCue({
      type: 'danger',
      message: 'Clear close pockets before deep.',
      durationMs: 1200
    });
    return;
  }

  Drill.setHUD({
    score: score,
    message: 'Now clear the deep angle.'
  });
});

Drill.onEnemyHit(leftEnemy, function() {
  leftCleared = true;
  score += 2;

  Drill.setHUD({
    score: score,
    message: 'Left pocket cleared. Now isolate the right pocket.'
  });
});

Drill.onEnemyHit(rightEnemy, function() {
  rightCleared = true;
  score += 2;

  Drill.setHUD({
    score: score,
    message: 'Right pocket cleared. Now clear deep.'
  });
});

Drill.onEnemyHit(deepEnemy, function() {
  if (!leftCleared || !rightCleared) {
    mistakes += 1;
  }

  deepCleared = true;
  score += 3;

  Drill.complete({
    score: score,
    message: mistakes === 0 ? 'Clean slice-the-pie clear.' : 'Completed, but you exposed too many angles.',
    passed: mistakes === 0
  });
});

Drill.after(${t.timeoutMs + 7000}, function() {
  if (!deepCleared) {
    Drill.complete({
      score: score,
      message: 'Too slow. You did not finish the angle clear.',
      passed: false
    });
  }
});
`.trim();
    },
  },

  {
    id: 'headshot_focus',
    title: 'Headshot Focus',
    arena_preset: 'crossfire_clear',
    description: 'Stabilize your crosshair before committing after movement.',
    best_for: [
      'headshot percentage',
      'crosshair control',
      'post-movement aim',
      'fight conversion',
    ],
    script(choice) {
      const t = timing(choice);
      const title = safeTitle(choice, 'Headshot Focus');

      return `
var score = 0;
var mistakes = 0;
var stabilized = false;
var hits = 0;

Drill.setPlayerSpawn('player_start');

Drill.setObjective({
  title: ${JSON.stringify(title)},
  details: 'Do not shoot instantly after movement. Stabilize first, then take the fight cleanly.',
  requiredActions: ['stabilize', 'confirm_crosshair']
});

var enemyA = Drill.spawnEnemyAt('left_crossfire', {
  behavior: 'hold_angle',
  label: 'left target',
  reactionMs: ${t.enemyReactionMs}
});

var enemyB = Drill.spawnEnemyAt('right_crossfire', {
  behavior: 'hold_angle',
  label: 'right target',
  reactionMs: ${t.enemyReactionMs}
});

Drill.addActionPrompt({
  id: 'stabilize',
  key: '1',
  label: 'Stabilize crosshair',
  hint: 'Pause your aim before shooting',
  removeOnUse: false
});

Drill.addActionPrompt({
  id: 'confirm_crosshair',
  key: '2',
  label: 'Confirm headline',
  hint: 'Only then commit to the fight',
  removeOnUse: false
});

Drill.onMiss(function() {
  mistakes += 1;
  Drill.setHUD({
    score: score,
    message: 'Miss registered. Slow down and stabilize.'
  });
});

Drill.onAction('stabilize', function() {
  stabilized = true;
  score += 1;
  Drill.markActionComplete('stabilize');

  Drill.emitCue({
    type: 'info',
    message: 'Crosshair stabilized — prepare for swing',
    durationMs: 1000
  });

  Drill.after(${t.cueMs}, function() {
    Drill.swingEnemy(enemyA, Drill.resolvePoint('isolate_left'), ${t.swingSpeed});
    Drill.swingEnemy(enemyB, Drill.resolvePoint('isolate_right'), ${t.swingSpeed});
  });

  Drill.setHUD({
    score: score,
    message: 'Stabilized. Take clean shots.'
  });
});

Drill.onAction('confirm_crosshair', function() {
  if (!stabilized) {
    mistakes += 1;
    Drill.emitCue({
      type: 'danger',
      message: 'You confirmed before stabilizing.',
      durationMs: 1200
    });
    return;
  }

  Drill.markActionComplete('confirm_crosshair');
  Drill.setHUD({
    score: score,
    message: 'Shoot only after your crosshair is set.'
  });
});

Drill.onAnyEnemyHit(function() {
  hits += 1;
  score += 2;

  if (hits >= 2) {
    Drill.complete({
      score: score,
      message: mistakes === 0 ? 'Clean headshot-focus sequence.' : 'Completed, but accuracy discipline slipped.',
      passed: mistakes <= 1
    });
  }
});

Drill.after(${t.timeoutMs}, function() {
  Drill.complete({
    score: score,
    message: 'Too slow. You did not finish both fights.',
    passed: false
  });
});
`.trim();
    },
  },

  {
    id: 'jump_peek_info',
    title: 'Jump Peek Info',
    arena_preset: 'jump_peek_info_lane',
    description: 'Gather information without overcommitting into a long angle.',
    best_for: [
      'info gathering',
      'operator avoidance',
      'long angle discipline',
      'jump peeking',
    ],
    script(choice) {
      const t = timing(choice);
      const title = safeTitle(choice, 'Jump Peek Info');

      return `
var score = 0;
var mistakes = 0;
var infoGathered = false;
var committed = false;

Drill.setPlayerSpawn('player_start');

Drill.setObjective({
  title: ${JSON.stringify(title)},
  details: 'Gather info first, then decide whether to take or avoid the fight.',
  requiredActions: ['jump_peek_info', 'choose_commit']
});

var visibleEnemy = Drill.spawnEnemyAt('info_lane_mid', {
  behavior: 'hold_angle',
  label: 'visible contact',
  reactionMs: ${t.enemyReactionMs}
});

var deepEnemy = Drill.spawnEnemyAt('operator_angle', {
  behavior: 'hold_angle',
  label: 'deep threat',
  reactionMs: ${t.enemyReactionMs}
});

Drill.addActionPrompt({
  id: 'jump_peek_info',
  key: '1',
  label: 'Jump peek info',
  hint: 'Gather info without committing',
  removeOnUse: false
});

Drill.addActionPrompt({
  id: 'choose_commit',
  key: '2',
  label: 'Commit after info',
  hint: 'Only commit after the info cue',
  removeOnUse: false
});

Drill.onAction('jump_peek_info', function() {
  infoGathered = true;
  score += 1;
  Drill.markActionComplete('jump_peek_info');

  Drill.emitCueAt('operator_angle', {
    type: 'danger',
    message: 'Deep threat spotted — do not dry swing',
    durationMs: 1200
  });

  Drill.setHUD({
    score: score,
    message: 'Info gathered. Choose your fight carefully.'
  });
});

Drill.onAction('choose_commit', function() {
  if (!infoGathered) {
    mistakes += 1;
    Drill.emitCue({
      type: 'danger',
      message: 'You committed without info.',
      durationMs: 1200
    });
    return;
  }

  committed = true;
  Drill.markActionComplete('choose_commit');

  Drill.swingEnemy(visibleEnemy, Drill.resolvePoint('info_lane_deep'), ${t.swingSpeed});

  Drill.setHUD({
    score: score,
    message: 'Commit only to the isolated contact.'
  });
});

Drill.onEnemyHit(visibleEnemy, function() {
  if (!committed) {
    mistakes += 1;
  }

  score += 2;

  Drill.complete({
    score: score,
    message: mistakes === 0 ? 'Clean info-first fight.' : 'Completed, but you overcommitted early.',
    passed: mistakes === 0
  });
});

Drill.onEnemyHit(deepEnemy, function() {
  mistakes += 1;

  Drill.complete({
    score: score,
    message: 'You took the deep threat instead of using the info safely.',
    passed: false
  });
});

Drill.after(${t.timeoutMs}, function() {
  Drill.complete({
    score: score,
    message: 'Too slow. You gathered info but did not make a clean decision.',
    passed: false
  });
});
`.trim();
    },
  },

  {
    id: 'first_fight_control',
    title: 'First Fight Control',
    arena_preset: 'entry_smoke_lane',
    description: 'Take first contact without panic-swinging into multiple angles.',
    best_for: [
      'entry timing',
      'first fight',
      'overcommitting',
      'duelist mechanics',
    ],
    script(choice) {
      const t = timing(choice);
      const title = safeTitle(choice, 'First Fight Control');

      return `
var score = 0;
var mistakes = 0;
var ready = false;
var hitCount = 0;

Drill.setPlayerSpawn('player_start');

Drill.setObjective({
  title: ${JSON.stringify(title)},
  details: 'Take first contact, stabilize, then clear the second threat. Do not sprint into both angles.',
  requiredActions: ['ready_first_fight', 'stabilize_after_contact']
});

var firstEnemy = Drill.spawnEnemyAt('close_left', {
  behavior: 'hold_angle',
  label: 'first contact',
  reactionMs: ${t.enemyReactionMs}
});

var secondEnemy = Drill.spawnEnemyAt('site_right', {
  behavior: 'hold_angle',
  label: 'second contact',
  reactionMs: ${t.enemyReactionMs}
});

Drill.addActionPrompt({
  id: 'ready_first_fight',
  key: '1',
  label: 'Ready first fight',
  hint: 'Set your crosshair before entry contact',
  removeOnUse: false
});

Drill.addActionPrompt({
  id: 'stabilize_after_contact',
  key: '2',
  label: 'Stabilize after contact',
  hint: 'Reset before the second fight',
  removeOnUse: false
});

Drill.onAction('ready_first_fight', function() {
  ready = true;
  score += 1;
  Drill.markActionComplete('ready_first_fight');

  Drill.emitCueAt('close_left', {
    type: 'danger',
    message: 'First contact swinging',
    durationMs: 1000
  });

  Drill.after(${t.cueMs}, function() {
    Drill.swingEnemy(firstEnemy, Drill.resolvePoint('dash_exit'), ${t.swingSpeed});
  });

  Drill.setHUD({
    score: score,
    message: 'First fight prepared.'
  });
});

Drill.onAction('stabilize_after_contact', function() {
  if (hitCount < 1) {
    mistakes += 1;
    Drill.emitCue({
      type: 'danger',
      message: 'Stabilize after the first contact, not before.',
      durationMs: 1100
    });
    return;
  }

  Drill.markActionComplete('stabilize_after_contact');

  Drill.emitCueAt('site_right', {
    type: 'danger',
    message: 'Second contact active',
    durationMs: 900
  });

  Drill.after(${t.cueMs}, function() {
    Drill.swingEnemy(secondEnemy, Drill.resolvePoint('deep_site'), ${t.swingSpeed});
  });
});

Drill.onEnemyHit(firstEnemy, function() {
  if (!ready) {
    mistakes += 1;
  }

  hitCount += 1;
  score += 2;

  Drill.setHUD({
    score: score,
    message: 'First fight won. Reset before the next.'
  });
});

Drill.onEnemyHit(secondEnemy, function() {
  hitCount += 1;
  score += 2;

  Drill.complete({
    score: score,
    message: mistakes === 0 ? 'Clean first-fight control.' : 'Completed, but your fight pacing was messy.',
    passed: mistakes === 0
  });
});

Drill.after(${t.timeoutMs + 3000}, function() {
  Drill.complete({
    score: score,
    message: 'Too slow. You failed to convert both fights.',
    passed: false
  });
});
`.trim();
    },
  },

  {
    id: 'trade_timing',
    title: 'Trade Timing',
    arena_preset: 'crossfire_clear',
    description: 'Wait for the contact cue, then trade instead of swinging alone.',
    best_for: ['team conversion', 'trading', 'patience', 'round conversion'],
    script(choice) {
      const t = timing(choice);
      const title = safeTitle(choice, 'Trade Timing');

      return `
var score = 0;
var mistakes = 0;
var contactCalled = false;

Drill.setPlayerSpawn('player_start');

Drill.setObjective({
  title: ${JSON.stringify(title)},
  details: 'Do not swing alone. Wait for contact, then trade the enemy movement.',
  requiredActions: ['wait_contact', 'trade_swing']
});

var enemy = Drill.spawnEnemyAt('left_crossfire', {
  behavior: 'hold_angle',
  label: 'trade target',
  reactionMs: ${t.enemyReactionMs}
});

Drill.addActionPrompt({
  id: 'wait_contact',
  key: '1',
  label: 'Wait for contact',
  hint: 'Let the contact cue happen first',
  removeOnUse: false
});

Drill.addActionPrompt({
  id: 'trade_swing',
  key: '2',
  label: 'Trade swing',
  hint: 'Swing after contact',
  removeOnUse: false
});

Drill.onAction('wait_contact', function() {
  contactCalled = true;
  score += 1;
  Drill.markActionComplete('wait_contact');

  Drill.emitCue({
    type: 'audio',
    message: 'Teammate contact — trade now',
    durationMs: 1200
  });

  Drill.after(${t.cueMs}, function() {
    Drill.swingEnemy(enemy, Drill.resolvePoint('right_crossfire'), ${t.swingSpeed});
  });

  Drill.setHUD({
    score: score,
    message: 'Contact cue active. Trade the fight.'
  });
});

Drill.onAction('trade_swing', function() {
  if (!contactCalled) {
    mistakes += 1;
    Drill.emitCue({
      type: 'danger',
      message: 'Too early — you swung without contact.',
      durationMs: 1200
    });
    return;
  }

  Drill.markActionComplete('trade_swing');
});

Drill.onEnemyHit(enemy, function() {
  score += 2;

  Drill.complete({
    score: score,
    message: mistakes === 0 ? 'Clean trade timing.' : 'Completed, but you swung too early.',
    passed: mistakes === 0
  });
});

Drill.after(${t.timeoutMs}, function() {
  Drill.complete({
    score: score,
    message: 'Too slow. You missed the trade window.',
    passed: false
  });
});
`.trim();
    },
  },

  {
    id: 'post_plant_discipline',
    title: 'Post-Plant Discipline',
    arena_preset: 'postplant_box_site',
    description: 'Play the spike/plant timing instead of overheating after advantage.',
    best_for: ['post-plant', 'round conversion', 'overheating', 'discipline'],
    script(choice) {
      const t = timing(choice);
      const title = safeTitle(choice, 'Post-Plant Discipline');

      return `
var score = 0;
var mistakes = 0;
var tapWaited = false;
var hits = 0;

Drill.setPlayerSpawn('safe_postplant');

Drill.setObjective({
  title: ${JSON.stringify(title)},
  details: 'Do not chase. Wait for the tap cue, then punish the retake timing.',
  requiredActions: ['play_time', 'punish_tap']
});

var tapper = Drill.spawnEnemyAt('tap_enemy', {
  behavior: 'hold_angle',
  label: 'tap enemy',
  reactionMs: ${t.enemyReactionMs}
});

var retaker = Drill.spawnEnemyAt('right_retaker', {
  behavior: 'hold_angle',
  label: 'retaker',
  reactionMs: ${t.enemyReactionMs}
});

Drill.addActionPrompt({
  id: 'play_time',
  key: '1',
  label: 'Play time',
  hint: 'Hold discipline instead of chasing',
  removeOnUse: false
});

Drill.addActionPrompt({
  id: 'punish_tap',
  key: '2',
  label: 'Punish tap',
  hint: 'Swing on the tap cue',
  removeOnUse: false
});

Drill.onAction('play_time', function() {
  tapWaited = true;
  score += 1;
  Drill.markActionComplete('play_time');

  Drill.emitCueAt('default_plant', {
    type: 'spike',
    message: 'Tap cue — punish timing',
    durationMs: 1200
  });

  Drill.after(${t.cueMs}, function() {
    Drill.swingEnemy(tapper, Drill.resolvePoint('swing_timing'), ${t.swingSpeed});
  });

  Drill.setHUD({
    score: score,
    message: 'Play time. Punish the tap.'
  });
});

Drill.onAction('punish_tap', function() {
  if (!tapWaited) {
    mistakes += 1;
    Drill.emitCue({
      type: 'danger',
      message: 'Too early — you chased before the tap.',
      durationMs: 1200
    });
    return;
  }

  Drill.markActionComplete('punish_tap');

  Drill.after(700, function() {
    Drill.swingEnemy(retaker, Drill.resolvePoint('left_retaker'), ${t.swingSpeed});
  });
});

Drill.onAnyEnemyHit(function() {
  hits += 1;
  score += 2;

  if (hits >= 2) {
    Drill.complete({
      score: score,
      message: mistakes === 0 ? 'Clean post-plant discipline.' : 'Completed, but you overheated early.',
      passed: mistakes === 0
    });
  }
});

Drill.after(${t.timeoutMs + 5000}, function() {
  Drill.complete({
    score: score,
    message: 'Too slow. You failed to convert the post-plant.',
    passed: false
  });
});
`.trim();
    },
  },

  {
    id: 'reposition_after_contact',
    title: 'Reposition After Contact',
    arena_preset: 'crossfire_clear',
    description:
      'After first contact, move/reset instead of taking the next fight from the same spot.',
    best_for: [
      'repositioning',
      'survival',
      'multi-kill discipline',
      'anti-overheat',
    ],
    script(choice) {
      const t = timing(choice);
      const title = safeTitle(choice, 'Reposition After Contact');

      return `
var score = 0;
var mistakes = 0;
var firstDone = false;
var repositioned = false;

Drill.setPlayerSpawn('player_start');

Drill.setObjective({
  title: ${JSON.stringify(title)},
  details: 'Win first contact, reposition, then take the second fight from a safer angle.',
  requiredActions: ['take_first', 'reposition']
});

var firstEnemy = Drill.spawnEnemyAt('left_crossfire', {
  behavior: 'hold_angle',
  label: 'first contact',
  reactionMs: ${t.enemyReactionMs}
});

var secondEnemy = Drill.spawnEnemyAt('deep_anchor', {
  behavior: 'hold_angle',
  label: 'second contact',
  reactionMs: ${t.enemyReactionMs}
});

Drill.addActionPrompt({
  id: 'take_first',
  key: '1',
  label: 'Take first contact',
  hint: 'Prepare for the first swing',
  removeOnUse: false
});

Drill.addActionPrompt({
  id: 'reposition',
  key: '2',
  label: 'Reposition',
  hint: 'Reset before the second fight',
  removeOnUse: false
});

Drill.onAction('take_first', function() {
  Drill.markActionComplete('take_first');

  Drill.emitCueAt('left_crossfire', {
    type: 'danger',
    message: 'First contact swinging',
    durationMs: 1000
  });

  Drill.after(${t.cueMs}, function() {
    Drill.swingEnemy(firstEnemy, Drill.resolvePoint('isolate_left'), ${t.swingSpeed});
  });
});

Drill.onEnemyHit(firstEnemy, function() {
  firstDone = true;
  score += 2;

  Drill.setHUD({
    score: score,
    message: 'First contact won. Reposition before next fight.'
  });
});

Drill.onAction('reposition', function() {
  if (!firstDone) {
    mistakes += 1;
    Drill.emitCue({
      type: 'danger',
      message: 'Reposition after first contact, not before.',
      durationMs: 1200
    });
    return;
  }

  repositioned = true;
  score += 1;
  Drill.markActionComplete('reposition');

  Drill.emitCueAt('deep_anchor', {
    type: 'danger',
    message: 'Second contact swinging',
    durationMs: 1000
  });

  Drill.after(${t.cueMs}, function() {
    Drill.swingEnemy(secondEnemy, Drill.resolvePoint('isolate_right'), ${t.swingSpeed});
  });
});

Drill.onEnemyHit(secondEnemy, function() {
  if (!repositioned) {
    mistakes += 1;
  }

  score += 2;

  Drill.complete({
    score: score,
    message: mistakes === 0 ? 'Clean reposition after contact.' : 'Completed, but you fought from a stale angle.',
    passed: mistakes === 0
  });
});

Drill.after(${t.timeoutMs + 4000}, function() {
  Drill.complete({
    score: score,
    message: 'Too slow. You did not finish the reposition sequence.',
    passed: false
  });
});
`.trim();
    },
  },
];

function templateCatalogForPrompt() {
  return MECHANIC_TEMPLATES.map(template => ({
    template_id: template.id,
    title: template.title,
    arena_preset: template.arena_preset,
    description: template.description,
    best_for: template.best_for,
  }));
}

function getTemplate(id: string | undefined, fallbackIndex: number) {
  return (
    MECHANIC_TEMPLATES.find(template => template.id === id) ??
    MECHANIC_TEMPLATES[fallbackIndex % MECHANIC_TEMPLATES.length]
  );
}

function compileScenarioTask(choice: TemplateChoice, index: number) {
  const template = getTemplate(choice.template_id, index);
  const title = safeTitle(choice, template.title);
  const description = safeDescription(choice, template.description);
  const linkedWeakness = safeWeakness(choice, template.best_for.join(', '));
  const script = template.script({ ...choice, title });

  return {
    title,
    description,
    type: 'scenario',
    config: {
      kind: 'scenario_script',
      arena_preset: template.arena_preset,
      drill_name: title,
      drill_instructions: description,
      linked_weakness: linkedWeakness,
      drill_script: scriptIsInvalid(script) ? fallbackScript(title) : script,
    },
  };
}

function fallbackGamesenseScenario(role: string) {
  return {
    technique: 'round conversion',
    round_type: 'full_buy',
    your_role: role || 'Player',
    situation:
      'You get the opening kill and your team has numbers advantage. The enemy can still punish a solo chase.',
    intel: [
      'Your team has numbers advantage.',
      'The enemy is waiting for mistakes.',
      'You can group, hold, or chase.',
    ],
    options: [
      {
        label: 'A',
        is_correct: false,
        reasoning:
          'Chasing alone risks giving the enemy a free trade and throwing the advantage.',
      },
      {
        label: 'B',
        is_correct: true,
        reasoning:
          'Regrouping and converting with the team preserves the advantage.',
      },
      {
        label: 'C',
        is_correct: false,
        reasoning:
          'Going passive without taking useful space may waste the opening kill.',
      },
      {
        label: 'D',
        is_correct: false,
        reasoning:
          'Ignoring the numbers advantage makes the round harder than necessary.',
      },
    ],
    time_limit_seconds: 15,
  };
}

function cleanGamesenseTask(raw: any, role: string) {
  const config = raw?.config ?? {};
  const scenarios =
    Array.isArray(config.scenarios) && config.scenarios.length > 0
      ? config.scenarios.slice(0, 3)
      : [fallbackGamesenseScenario(role)];

  return {
    title: raw?.title || 'Round Conversion',
    description:
      raw?.description ||
      'A gamesense drill focused on converting advantage into round wins.',
    type: 'gamesense',
    config: {
      kind: 'gamesense',
      linked_weakness:
        config.linked_weakness ||
        raw?.linked_weakness ||
        'Converting individual impact into round wins.',
      scenarios,
    },
  };
}

function compileTrainingTasks(raw: any, role: string) {
  const selected = Array.isArray(raw?.selected_templates)
    ? raw.selected_templates
    : [];

  const gamesense = raw?.gamesense_task ?? raw?.gamesense ?? null;

  const first = selected[0] ?? {
    template_id: 'jiggle_peek',
    title: 'Jiggle Peek',
    difficulty: 'medium',
  };

  const second = selected[1] ?? {
    template_id: 'slicing_the_pie',
    title: 'Slicing the Pie',
    difficulty: 'medium',
  };

  return [
    compileScenarioTask(first, 0),
    compileScenarioTask(second, 1),
    cleanGamesenseTask(gamesense, role),
  ];
}

export async function processCoachAnalysis(
  userId: string,
  mode: CoachMode
): Promise<AIResponse> {
  if (!userId) throw new Error('Missing User ID');

  const { data: matches, error: matchError } = await supabase
    .from('match_data')
    .select('data, map, agent, outcome, coach_notes')
    .eq('profile_id', userId)
    .order('played_at', { ascending: false })
    .limit(10);

  if (matchError) {
    throw new Error(`Match fetch failed: ${matchError.message}`);
  }

  const { data: savedSummary } = await supabase
    .from('ai_summaries')
    .select('*')
    .eq('profile_id', userId)
    .maybeSingle();

  const { data: playerStats, error: statsError } = await supabase
    .from('player_stats')
    .select(
      'kd_ratio, headshot_pct, win_rate, aim_score, gamesense_score, mechanics_score, playstyle_tags, agent_prefs, current_rank'
    )
    .eq('profile_id', userId)
    .order('synced_at', { ascending: false })
    .limit(1)
    .maybeSingle();

  if (statsError) {
    throw new Error(`Stats fetch failed: ${statsError.message}`);
  }

  const model = genAI.getGenerativeModel({
    model: 'gemini-2.5-flash',
    generationConfig: {
      responseMimeType: 'application/json',
    },
  });

  if (mode === 'summary') {
    const result = await model.generateContent(`
Expert Valorant coach. Analyze and return JSON only.
Also rate the level of the player from: Beginner, Intermediate, Experienced, High Elo, Top Tier, Pro
Be supportive but also honest at same time, not disrespectful

this should be based on experience and also player weakness/strengths
MATCHES:
${JSON.stringify(matches)}

STATS:
${JSON.stringify(playerStats)}

Return ONLY:
{
  "summary": "2-3 direct sentences with actual numbers",
  "rating": "beginner, intermediate, experienced, high elo, top tier, pro"
  "strengths": ["specific strength"],
  "weaknesses": ["specific weakness"]
}
`);

    const response: AIResponse = extractJSON(result.response.text());

    await supabase.from('ai_summaries').upsert({
      profile_id: userId,
      ...response,
      updated_at: new Date().toISOString(),
    });

    return response;
  }

  const prefs = (playerStats as any)?.agent_prefs ?? [];
  const topAgent = prefs[0]?.name ?? 'Player';
  const topRole = prefs[0]?.role ?? 'Player';
  const secAgent = prefs[1]?.name ?? topAgent;

  const rank = (playerStats as any)?.current_rank ?? 'Unrated';
  const aimScore = (playerStats as any)?.aim_score ?? 50;
  const mechScore = (playerStats as any)?.mechanics_score ?? 50;
  const gamesenseScore = (playerStats as any)?.gamesense_score ?? 50;
  const hsPercent = (playerStats as any)?.headshot_pct ?? 20;
  const kdRatio = (playerStats as any)?.kd_ratio ?? null;
  const winRate = (playerStats as any)?.win_rate ?? null;
  const playstyleTags = (playerStats as any)?.playstyle_tags ?? [];

  const strengths = savedSummary?.strengths ?? [];
  const weaknesses = savedSummary?.weaknesses ?? [];

  const arenaPresets = getPromptArenaPresets();
  const templateCatalog = templateCatalogForPrompt();

  const prompt = `
You are a Valorant mechanics coach.

You do NOT write executable drill JavaScript.
You only select from premade mechanics templates and generate gamesense questions.

The app owns all executable drill code.
You choose:
- 2 mechanics templates from the catalog
- titles
- descriptions
- difficulty
- linked weakness
- 1 gamesense task

PLAYER CONTEXT:
- Main Agent: ${topAgent}
- Secondary Agent: ${secAgent}
- Role: ${topRole}
- Rank: ${rank}
- KD: ${kdRatio}
- Win Rate: ${winRate}
- Aim: ${aimScore}/100
- Mechanics: ${mechScore}/100
- Gamesense: ${gamesenseScore}/100
- HS%: ${hsPercent}%
- Playstyle Tags: ${JSON.stringify(playstyleTags)}
- Strengths: ${JSON.stringify(strengths)}
- Weaknesses: ${JSON.stringify(weaknesses)}
- Recent Matches: ${JSON.stringify(matches)}

AVAILABLE MECHANICS TEMPLATES:
${JSON.stringify(templateCatalog, null, 2)}

AVAILABLE ARENA PRESETS:
${JSON.stringify(arenaPresets, null, 2)}

TITLE STYLE:
Use clear mechanic names.
Good examples:
- "Jiggle Peek"
- "Slicing the Pie"
- "Headshot Focus"
- "Crosshair Placement"
- "Jump Peek Info"
- "First Fight Control"
- "Trade Timing"
- "Post-Plant Discipline"
- "Reposition After Contact"

Do not use weird niche names.
Do not use long protocol names.
Do not use agent ability names.
Do not name a drill after a specific agent.

SELECTION RULES:
1. Select exactly 2 different mechanics templates.
2. Pick templates that best match the weaknesses.
3. If headshot percentage is weak, prefer "headshot_focus".
4. If win rate is weak despite good KD, prefer "post_plant_discipline", "trade_timing", or "reposition_after_contact".
5. If mechanics score is weak, prefer "jiggle_peek", "slicing_the_pie", or "first_fight_control".
6. If aggressive agent performance is weak, prefer "first_fight_control".
7. If angle clearing, exposed deaths, or poor clearing discipline is relevant, prefer "slicing_the_pie".
8. No abilities. No utility simulation. No raw scripts.
9. Difficulty must be "easy", "medium", or "hard".

GAMESENSE RULES:
The gamesense task should test decision-making, not mechanics.
Focus on:
- converting advantage
- avoiding overheat
- trading
- post-plant decisions
- retake choices
- playing numbers advantage

Return ONLY valid JSON:
{
  "selected_templates": [
    {
      "template_id": "one of the available template_id values",
      "title": "clear mechanic title",
      "description": "one sentence describing the drill",
      "difficulty": "easy | medium | hard",
      "linked_weakness": "specific weakness this targets",
      "focus": "short focus description"
    },
    {
      "template_id": "one of the available template_id values",
      "title": "clear mechanic title",
      "description": "one sentence describing the drill",
      "difficulty": "easy | medium | hard",
      "linked_weakness": "specific weakness this targets",
      "focus": "short focus description"
    }
  ],
  "gamesense_task": {
    "title": "clear gamesense title",
    "description": "one sentence",
    "type": "gamesense",
    "config": {
      "kind": "gamesense",
      "linked_weakness": "specific weakness this targets",
      "scenarios": [
        {
          "technique": "round conversion / anti-overheat / post-plant / retake / trade timing",
          "round_type": "full_buy",
          "your_role": "${topRole}",
          "situation": "Generic Valorant situation with no specific map name.",
          "intel": ["info 1", "info 2", "info 3"],
          "options": [
            {"label":"A","is_correct":false,"reasoning":"why"},
            {"label":"B","is_correct":true,"reasoning":"why"},
            {"label":"C","is_correct":false,"reasoning":"why"},
            {"label":"D","is_correct":false,"reasoning":"why"}
          ],
          "time_limit_seconds": 15
        }
      ]
    }
  }
}
`;

  const result = await model.generateContent(prompt);
  const parsed = extractJSON(result.response.text());

  const tasks = compileTrainingTasks(parsed, topRole);

  await supabase.from('training_tasks').delete().eq('user_id', userId);

  const { error } = await supabase.from('training_tasks').insert(
    tasks.map((task: any, i: number) => ({
      user_id: userId,
      title: task.title || `Drill ${i + 1}`,
      description: task.description || 'AI drill.',
      type: task.type || 'scenario',
      config: task.config,
    }))
  );

  if (error) {
    throw new Error(`DB insert failed: ${error.message}`);
  }

  return {
    suggested_tasks: tasks,
  };
}