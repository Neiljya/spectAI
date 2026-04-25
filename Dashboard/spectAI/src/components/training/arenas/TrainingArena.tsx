// src/components/training/arenas/TrainingArena.tsx

import * as THREE from 'three';
import { getArenaPreset } from './arenaPresets';

interface Props {
  arenaId?: string;
  groundColor?: string;
}

export function TrainingArena({ arenaId, groundColor = '#1a1a1a' }: Props) {
  const arena = getArenaPreset(arenaId);

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[arena.floorSize[0], arena.floorSize[2]]} />
        <meshStandardMaterial color={groundColor} roughness={0.9} />
      </mesh>

      {arena.walls.map(wall => (
        <mesh
          key={wall.id}
          position={wall.position}
          castShadow
          receiveShadow
          userData={{
            arenaWall: true,
            sandboxBlocker: true,
            wallId: wall.id,
          }}
        >
          <boxGeometry args={wall.scale} />
          <meshStandardMaterial color={wall.color ?? '#30343f'} roughness={0.85} />
        </mesh>
      ))}

      {arena.cover.map(cover => (
        <mesh
          key={cover.id}
          position={cover.position}
          castShadow
          receiveShadow
          userData={{
            arenaCover: true,
            sandboxBlocker: true,
            coverId: cover.id,
          }}
        >
          <boxGeometry args={cover.scale} />
          <meshStandardMaterial color={cover.color ?? '#555b66'} roughness={0.9} />
        </mesh>
      ))}

      {Object.values(arena.points).map(point => (
        <group key={point.id} position={point.position}>
          <mesh position={[0, -1.55, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[0.35, 0.42, 24]} />
            <meshBasicMaterial color="#ffffff" transparent opacity={0.12} />
          </mesh>
        </group>
      ))}

      <gridHelper
        args={[
          Math.max(arena.floorSize[0], arena.floorSize[2]),
          24,
          new THREE.Color('#ffffff'),
          new THREE.Color('#ffffff'),
        ]}
        position={[0, 0.015, 0]}
      />
    </group>
  );
}