// src/components/training/abilities/agentAbilities.ts

import type { AgentAbility } from './abilityTypes';

export const AGENT_ABILITIES: Record<string, AgentAbility[]> = {
  Jett: [
    {
      id: 'jett_tailwind',
      agent: 'Jett',
      slot: 'E',
      name: 'Tailwind',
      category: 'movement',
      description: 'Dash in a chosen direction to simulate entry timing or escape timing.',
      defaultKey: 'e',

      use(runtime, opts, ctx) {
        const distance = Number(opts.distance ?? 8);
        const direction = opts.direction ?? 'forward';

        let dx = 0;
        let dz = 0;

        if (direction === 'forward') dz = -distance;
        if (direction === 'backward') dz = distance;
        if (direction === 'left') dx = -distance;
        if (direction === 'right') dx = distance;

        runtime.emitCue({
          type: 'utility',
          message: 'Tailwind dash',
          position: ctx.playerPosition,
          durationMs: 900,
          color: '#9be7ff',
        });

        runtime.movePlayerBy([dx, 0, dz]);
      },
    },

    {
      id: 'jett_cloudburst',
      agent: 'Jett',
      slot: 'C',
      name: 'Cloudburst',
      category: 'smoke',
      description: 'Creates a temporary smoke zone for dash-entry or escape drills.',
      defaultKey: 'c',

      use(runtime, opts, ctx) {
        const position = opts.position ?? opts.targetPosition ?? [
          ctx.playerPosition[0],
          1,
          ctx.playerPosition[2] - 12,
        ];

        const radius = Number(opts.radius ?? 5);
        const durationMs = Number(opts.durationMs ?? 4500);

        const zoneName = `jett_cloudburst_${Date.now()}`;

        runtime.createZone({
          name: zoneName,
          position,
          scale: [radius, 3, radius],
          color: '#9be7ff',
          visible: true,
          label: 'Cloudburst',
        });

        runtime.emitCue({
          type: 'utility',
          message: 'Cloudburst smoke deployed',
          position,
          durationMs: 1200,
          color: '#9be7ff',
        });

        runtime.after(durationMs, () => {
          runtime.removeZone(zoneName);
        });
      },
    },
  ],

  Phoenix: [
    {
      id: 'phoenix_curveball',
      agent: 'Phoenix',
      slot: 'Q',
      name: 'Curveball',
      category: 'flash',
      description: 'Pops a flash cue and creates a short timing window to swing.',
      defaultKey: 'q',

      use(runtime, opts, ctx) {
        const position = opts.position ?? [
          ctx.playerPosition[0],
          1.6,
          ctx.playerPosition[2] - 8,
        ];

        runtime.emitCue({
          type: 'utility',
          message: 'Curveball popped — swing now',
          position,
          durationMs: 1200,
          color: '#ffd166',
        });

        runtime.createZone({
          name: `phoenix_flash_window_${Date.now()}`,
          position,
          scale: [5, 3, 5],
          color: '#ffd166',
          visible: true,
          label: 'Flash timing window',
        });
      },
    },

    {
      id: 'phoenix_hot_hands',
      agent: 'Phoenix',
      slot: 'E',
      name: 'Hot Hands',
      category: 'molly',
      description: 'Creates a denial zone that punishes enemies or blocks space.',
      defaultKey: 'e',

      use(runtime, opts, ctx) {
        const position = opts.position ?? [
          ctx.playerPosition[0],
          0.05,
          ctx.playerPosition[2] - 10,
        ];

        const zoneName = `phoenix_molly_${Date.now()}`;

        runtime.createZone({
          name: zoneName,
          position,
          scale: [5, 1, 5],
          color: '#ff7a1a',
          visible: true,
          label: 'Hot Hands',
        });

        runtime.emitCue({
          type: 'utility',
          message: 'Hot Hands blocking space',
          position,
          durationMs: 1200,
          color: '#ff7a1a',
        });

        runtime.after(Number(opts.durationMs ?? 4500), () => {
          runtime.removeZone(zoneName);
        });
      },
    },
  ],

  Omen: [
    {
      id: 'omen_dark_cover',
      agent: 'Omen',
      slot: 'E',
      name: 'Dark Cover',
      category: 'smoke',
      description: 'Creates a smoke zone to block an angle or enable a cross.',
      defaultKey: 'e',

      use(runtime, opts, ctx) {
        const position = opts.position ?? [
          ctx.playerPosition[0],
          1,
          ctx.playerPosition[2] - 18,
        ];

        const radius = Number(opts.radius ?? 6);
        const durationMs = Number(opts.durationMs ?? 6000);
        const zoneName = `omen_smoke_${Date.now()}`;

        runtime.createZone({
          name: zoneName,
          position,
          scale: [radius, 4, radius],
          color: '#6d5dfc',
          visible: true,
          label: 'Dark Cover',
        });

        runtime.emitCue({
          type: 'utility',
          message: 'Dark Cover placed',
          position,
          durationMs: 1200,
          color: '#8f7cff',
        });

        runtime.after(durationMs, () => {
          runtime.removeZone(zoneName);
        });
      },
    },

    {
      id: 'omen_shrouded_step',
      agent: 'Omen',
      slot: 'C',
      name: 'Shrouded Step',
      category: 'teleport',
      description: 'Teleports the player to a target position after a short delay.',
      defaultKey: 'c',

      use(runtime, opts, ctx) {
        const targetPosition = opts.targetPosition ?? [
          ctx.playerPosition[0] + 6,
          1.6,
          ctx.playerPosition[2] - 10,
        ];

        runtime.emitCue({
          type: 'utility',
          message: 'Shrouded Step channeling',
          position: ctx.playerPosition,
          durationMs: 850,
          color: '#8f7cff',
        });

        runtime.after(Number(opts.delayMs ?? 850), () => {
          runtime.teleportPlayer(targetPosition);
          runtime.emitCue({
            type: 'visual',
            message: 'Teleported — clear the new angle',
            position: targetPosition,
            durationMs: 1200,
            color: '#8f7cff',
          });
        });
      },
    },
  ],
};

export function getAbilitiesForAgent(agent: string) {
  return AGENT_ABILITIES[agent] ?? [];
}

export function getAbilityById(id: string) {
  for (const abilities of Object.values(AGENT_ABILITIES)) {
    const found = abilities.find(ability => ability.id === id);
    if (found) return found;
  }

  return null;
}