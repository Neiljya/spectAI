// src/components/training/abilities/abilityTypes.ts

export type Vec3 = [number, number, number];

export type AbilityCategory =
  | 'movement'
  | 'flash'
  | 'smoke'
  | 'recon'
  | 'molly'
  | 'stun'
  | 'wall'
  | 'teleport'
  | 'heal'
  | 'trap'
  | 'decoy'
  | 'ultimate';

export interface AbilityUseContext {
  playerPosition: Vec3;
  playerDirection: Vec3;
  now: number;
}

export interface AbilityUseOptions {
  position?: Vec3;
  targetPosition?: Vec3;
  direction?: 'forward' | 'backward' | 'left' | 'right';
  distance?: number;
  durationMs?: number;
  radius?: number;
  delayMs?: number;
  label?: string;
  [key: string]: unknown;
}

export interface AbilityRuntimeAPI {
  movePlayerBy(delta: Vec3): void;
  teleportPlayer(position: Vec3): void;

  emitCue(opts: {
    type?: 'audio' | 'visual' | 'utility' | 'spike' | 'danger' | 'info';
    message: string;
    position?: Vec3;
    durationMs?: number;
    color?: string;
  }): string;

  createZone(opts: {
    name: string;
    position: Vec3;
    scale?: Vec3;
    color?: string;
    visible?: boolean;
    label?: string;
  }): string;

  removeZone(idOrName: string): void;

  spawnCover(opts: {
    position: Vec3;
    scale?: Vec3;
    color?: string;
    label?: string;
  }): string;

  spawnEnemy(opts: any): string;
  swingEnemy(id: string, to: Vec3, speed?: number): void;
  fallBackEnemy(id: string, to: Vec3, speed?: number): void;
  setHUD(opts: any): void;
  after(ms: number, cb: () => void): number;
}

export interface AgentAbility {
  id: string;
  agent: string;
  slot: 'C' | 'Q' | 'E' | 'X' | 'Passive';
  name: string;
  category: AbilityCategory;
  description: string;
  defaultKey: string;

  use: (
    runtime: AbilityRuntimeAPI,
    opts: AbilityUseOptions,
    ctx: AbilityUseContext
  ) => void;
}