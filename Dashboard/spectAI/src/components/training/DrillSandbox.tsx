import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { PointerLockControls, Sky } from '@react-three/drei';
import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  type MutableRefObject,
} from 'react';
import * as THREE from 'three';
import type { AimDrillTask } from './engineTypes';
import { getAbilityById } from './abilities/agentAbilities';
import { getArenaPreset, resolveArenaPoint } from './arenas/arenaPresets';
import { TrainingArena } from './arenas/TrainingArena';
import './DrillSandbox.css';

type Vec3 = [number, number, number];
type Axis = 'x' | 'y' | 'z';

type EnemyBehavior =
  | 'hold_angle'
  | 'swing'
  | 'jiggle'
  | 'fall_back'
  | 'decoy'
  | 'idle';

type CueType =
  | 'audio'
  | 'visual'
  | 'utility'
  | 'spike'
  | 'danger'
  | 'info';

type SafeCall = (
  label: string,
  cb: (...args: any[]) => void,
  ...args: any[]
) => void;

interface Bounds3 {
  x?: [number, number];
  y?: [number, number];
  z?: [number, number];
}

interface SpawnOpts {
  position: Vec3;
  size?: number;
  color?: string;
  velocity?: Vec3;
  bounds?: Bounds3;
  label?: string;
}

interface EnemyOpts {
  position: Vec3;
  label?: string;
  behavior?: EnemyBehavior;
  size?: number;
  color?: string;
  hp?: number;
  reactionMs?: number;
  weapon?: string;
  velocity?: Vec3;
  bounds?: Bounds3;
  hiddenPosition?: Vec3;
  swingTo?: Vec3;
  swingSpeed?: number;
}

interface CoverOpts {
  position: Vec3;
  scale?: Vec3;
  color?: string;
  label?: string;
}

interface ZoneOpts {
  name: string;
  position: Vec3;
  scale?: Vec3;
  color?: string;
  visible?: boolean;
  label?: string;
  shape?: 'box' | 'sphere';
}

interface CueOpts {
  type?: CueType;
  message: string;
  position?: Vec3;
  durationMs?: number;
  color?: string;
}

interface ActionPromptOpts {
  id?: string;
  key: string;
  label: string;
  hint?: string;
  expiresMs?: number;
  removeOnUse?: boolean;
}

interface AbilityBindOpts {
  id?: string;
  abilityId: string;
  key: string;
  label?: string;
  hint?: string;
  options?: Record<string, unknown>;
  expiresMs?: number;
  removeOnUse?: boolean;
}

interface ObjectiveOpts {
  title?: string;
  details?: string;
  requiredActions?: string[];
}

interface HUDOpts {
  score?: number;
  message?: string;
  hint?: string;
  timeLeft?: number;
}

interface CompletionStats {
  score?: number;
  message?: string;
  passed?: boolean;
  [key: string]: unknown;
}

interface TargetData {
  id: string;
  position: THREE.Vector3;
  size: number;
  color: string;
  velocity?: THREE.Vector3;
  bounds?: Bounds3;
  label?: string;
}

interface EnemyData {
  id: string;
  position: THREE.Vector3;
  basePosition: THREE.Vector3;
  targetPosition?: THREE.Vector3;
  velocity?: THREE.Vector3;
  bounds?: Bounds3;
  behavior: EnemyBehavior;
  size: number;
  color: string;
  label: string;
  hp: number;
  maxHp: number;
  reactionMs: number;
  weapon?: string;
  alive: boolean;
  jiggleAxis: Axis;
  jiggleAmount: number;
  jiggleSpeed: number;
  moveSpeed: number;
}

interface CoverData {
  id: string;
  position: THREE.Vector3;
  scale: THREE.Vector3;
  color: string;
  label?: string;
}

interface ZoneData {
  id: string;
  name: string;
  position: THREE.Vector3;
  scale: THREE.Vector3;
  color: string;
  visible: boolean;
  label?: string;
  shape: 'box' | 'sphere';
}

interface CueData {
  id: string;
  type: CueType;
  message: string;
  position?: THREE.Vector3;
  color: string;
}

interface ActionPromptData {
  id: string;
  key: string;
  label: string;
  hint?: string;
  removeOnUse: boolean;
}

interface AbilityBindingData {
  actionId: string;
  abilityId: string;
  options: Record<string, unknown>;
}

interface ObjectiveData {
  title?: string;
  details?: string;
  requiredActions: string[];
  completedActions: string[];
}

interface PlayerState {
  position: THREE.Vector3;
  direction: THREE.Vector3;
  insideZones: Set<string>;
  lastShotAt: number;
}

interface Callbacks {
  hit: Map<string, (id: string) => void>;
  anyHit: ((id: string) => void)[];

  enemyHit: Map<string, (id: string) => void>;
  anyEnemyHit: ((id: string) => void)[];

  miss: (() => void)[];
  tick: ((dt: number, elapsed: number) => void)[];

  action: Map<string, ((id: string) => void)[]>;
  anyAction: ((id: string) => void)[];

  zoneEnter: Map<string, ((zoneName: string) => void)[]>;

  timers: ReturnType<typeof setTimeout>[];
  intervals: ReturnType<typeof setInterval>[];
}

interface SandboxHUD {
  score?: number;
  message?: string;
  hint?: string;
  timeLeft?: number;
}

interface Props {
  config: AimDrillTask;
  onComplete: (stats: CompletionStats) => void;
}

const THEMES: Record<
  string,
  {
    sky: [number, number, number, number, number];
    ground: string;
    wall: string;
    fog: string;
    ambient: number;
  }
> = {
  ascent: {
    sky: [0.5, 2, 0.3, 2, 0.5],
    ground: '#b5b3ae',
    wall: '#d4c9b0',
    fog: '#c0bdb7',
    ambient: 0.7,
  },
  fracture: {
    sky: [8, 1, 0.5, 2, 0.4],
    ground: '#4a3f35',
    wall: '#5c4e42',
    fog: '#2a2018',
    ambient: 0.5,
  },
  bind: {
    sky: [2, 0.5, 0.2, 1, 0.3],
    ground: '#8c7355',
    wall: '#a08060',
    fog: '#6b5540',
    ambient: 0.55,
  },
  haven: {
    sky: [0.5, 1.5, 0.4, 2, 0.4],
    ground: '#c4bfb8',
    wall: '#d8d0c8',
    fog: '#b0aaa0',
    ambient: 0.7,
  },
  split: {
    sky: [6, 0.5, 0.3, 1, 0.3],
    ground: '#2a2a2a',
    wall: '#3a3a3a',
    fog: '#111',
    ambient: 0.4,
  },
  default: {
    sky: [0.5, 1, 0.3, 1, 0.5],
    ground: '#1a1a1a',
    wall: '#2a2a2a',
    fog: '#0a0a0a',
    ambient: 0.5,
  },
};

function getTheme(themeName?: string) {
  const key =
    Object.keys(THEMES).find(k => themeName?.toLowerCase().includes(k)) ??
    'default';

  return THEMES[key];
}

function makeId(prefix = '') {
  return `${prefix}${Math.random().toString(36).slice(2, 10)}`;
}

function isVec3(value: unknown): value is Vec3 {
  return (
    Array.isArray(value) &&
    value.length === 3 &&
    value.every(n => typeof n === 'number' && Number.isFinite(n))
  );
}

function safeVec3(value: unknown, fallback: Vec3): Vec3 {
  return isVec3(value) ? value : fallback;
}

function safeNumber(value: unknown, fallback: number) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function safeBounds(value: unknown): Bounds3 | undefined {
  if (!value || typeof value !== 'object') return undefined;
  return value as Bounds3;
}

function toVec3(value: THREE.Vector3): Vec3 {
  return [value.x, value.y, value.z];
}

function moveToward(
  current: THREE.Vector3,
  target: THREE.Vector3,
  maxStep: number
) {
  const delta = target.clone().sub(current);
  const dist = delta.length();

  if (dist <= maxStep || dist < 0.001) {
    current.copy(target);
    return true;
  }

  current.add(delta.normalize().multiplyScalar(maxStep));
  return false;
}

function inZone(point: THREE.Vector3, zone: ZoneData) {
  return (
    Math.abs(point.x - zone.position.x) <= zone.scale.x / 2 &&
    Math.abs(point.y - zone.position.y) <= Math.max(zone.scale.y / 2, 2) &&
    Math.abs(point.z - zone.position.z) <= zone.scale.z / 2
  );
}

function applyBounds(
  position: THREE.Vector3,
  velocity: THREE.Vector3,
  bounds?: Bounds3
) {
  const b = bounds ?? {};

  (['x', 'y', 'z'] as const).forEach(axis => {
    const range = b[axis];
    if (!range) return;

    if (position[axis] < range[0]) {
      position[axis] = range[0];
      velocity[axis] *= -1;
    }

    if (position[axis] > range[1]) {
      position[axis] = range[1];
      velocity[axis] *= -1;
    }
  });
}

function SandboxTargetMesh({
  id,
  targetsRef,
  callbacksRef,
  safeCall,
}: {
  id: string;
  targetsRef: MutableRefObject<Map<string, TargetData>>;
  callbacksRef: MutableRefObject<Callbacks>;
  safeCall: SafeCall;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const matRef = useRef<THREE.MeshStandardMaterial>(null);
  const flash = useRef(false);
  const flashT = useRef(0);

  useFrame((state, delta) => {
    const target = targetsRef.current.get(id);
    if (!target || !meshRef.current || !matRef.current) return;

    if (target.velocity) {
      target.position.addScaledVector(target.velocity, delta);
      applyBounds(target.position, target.velocity, target.bounds);
    }

    meshRef.current.position.copy(target.position);

    if (!target.velocity) {
      meshRef.current.position.y =
        target.position.y +
        Math.sin(state.clock.getElapsedTime() * 1.6 + target.position.x * 0.5) *
          0.04;
    }

    if (flash.current) {
      const age = state.clock.getElapsedTime() - flashT.current;

      matRef.current.emissiveIntensity = Math.max(1.2, 5 - age * 25);
      matRef.current.color.set(age < 0.06 ? '#ffffff' : target.color);

      if (age > 0.15) {
        flash.current = false;
      }
    }
  });

  const target = targetsRef.current.get(id);
  if (!target) return null;

  function triggerHit() {
    flash.current = true;
    flashT.current = performance.now() / 1000;

    const specific = callbacksRef.current.hit.get(id);
    if (specific) safeCall(`onHit:${id}`, specific, id);

    callbacksRef.current.anyHit.forEach(cb => {
      safeCall('onAnyHit', cb, id);
    });
  }

  return (
    <mesh
      ref={meshRef}
      position={target.position.toArray() as Vec3}
      userData={{
        sandboxClickable: true,
        sandboxKind: 'target',
        sandboxId: id,
        triggerHit,
      }}
    >
      <sphereGeometry args={[target.size, 22, 22]} />
      <meshStandardMaterial
        ref={matRef}
        color={target.color}
        emissive={target.color}
        emissiveIntensity={1.2}
        metalness={0.4}
        roughness={0.3}
      />
    </mesh>
  );
}

function EnemyMesh({
  id,
  enemiesRef,
  callbacksRef,
  safeCall,
  rerender,
}: {
  id: string;
  enemiesRef: MutableRefObject<Map<string, EnemyData>>;
  callbacksRef: MutableRefObject<Callbacks>;
  safeCall: SafeCall;
  rerender: () => void;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const bodyMatRef = useRef<THREE.MeshStandardMaterial>(null);
  const headMatRef = useRef<THREE.MeshStandardMaterial>(null);
  const flash = useRef(false);
  const flashT = useRef(0);

  useFrame((state, delta) => {
    const enemy = enemiesRef.current.get(id);
    if (!enemy || !groupRef.current || !enemy.alive) return;

    if (enemy.velocity) {
      enemy.position.addScaledVector(enemy.velocity, delta);
      applyBounds(enemy.position, enemy.velocity, enemy.bounds);
    }

    if (
      (enemy.behavior === 'swing' || enemy.behavior === 'fall_back') &&
      enemy.targetPosition
    ) {
      moveToward(enemy.position, enemy.targetPosition, enemy.moveSpeed * delta);
    }

    if (enemy.behavior === 'jiggle') {
      const t = state.clock.getElapsedTime() * enemy.jiggleSpeed;

      enemy.position.copy(enemy.basePosition);
      enemy.position[enemy.jiggleAxis] += Math.sin(t) * enemy.jiggleAmount;
    }

    groupRef.current.position.copy(enemy.position);

    if (flash.current) {
      const age = state.clock.getElapsedTime() - flashT.current;
      const color = age < 0.08 ? '#ffffff' : enemy.color;

      if (bodyMatRef.current) {
        bodyMatRef.current.emissiveIntensity = Math.max(0.8, 4 - age * 20);
        bodyMatRef.current.color.set(color);
      }

      if (headMatRef.current) {
        headMatRef.current.emissiveIntensity = Math.max(0.8, 4 - age * 20);
        headMatRef.current.color.set(color);
      }

      if (age > 0.2) {
        flash.current = false;
      }
    }
  });

  const enemy = enemiesRef.current.get(id);
  if (!enemy || !enemy.alive) return null;

  function triggerEnemyHit() {
    const e = enemiesRef.current.get(id);
    if (!e || !e.alive) return;

    e.hp -= 1;

    flash.current = true;
    flashT.current = performance.now() / 1000;

    const specific = callbacksRef.current.enemyHit.get(id);
    if (specific) safeCall(`onEnemyHit:${id}`, specific, id);

    callbacksRef.current.anyEnemyHit.forEach(cb => {
      safeCall('onAnyEnemyHit', cb, id);
    });

    if (e.hp <= 0) {
      e.alive = false;
      enemiesRef.current.delete(id);
      rerender();
    }
  }

  return (
    <group ref={groupRef} position={enemy.position.toArray() as Vec3}>
      <mesh
        position={[0, 1.05 * enemy.size, 0]}
        userData={{
          sandboxClickable: true,
          sandboxKind: 'enemy',
          sandboxId: id,
          triggerEnemyHit,
        }}
      >
        <cylinderGeometry
          args={[0.36 * enemy.size, 0.42 * enemy.size, 1.35 * enemy.size, 16]}
        />
        <meshStandardMaterial
          ref={bodyMatRef}
          color={enemy.color}
          emissive={enemy.color}
          emissiveIntensity={0.25}
          roughness={0.5}
        />
      </mesh>

      <mesh
        position={[0, 1.86 * enemy.size, 0]}
        userData={{
          sandboxClickable: true,
          sandboxKind: 'enemy',
          sandboxId: id,
          triggerEnemyHit,
        }}
      >
        <sphereGeometry args={[0.24 * enemy.size, 16, 16]} />
        <meshStandardMaterial
          ref={headMatRef}
          color={enemy.color}
          emissive={enemy.color}
          emissiveIntensity={0.4}
          roughness={0.35}
        />
      </mesh>
    </group>
  );
}

function CoverMesh({ cover }: { cover: CoverData }) {
  return (
    <group position={cover.position.toArray() as Vec3}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={cover.scale.toArray() as Vec3} />
        <meshStandardMaterial color={cover.color} roughness={0.9} />
      </mesh>
    </group>
  );
}

function ZoneMesh({ zone }: { zone: ZoneData }) {
  if (!zone.visible) return null;

  return (
    <group position={zone.position.toArray() as Vec3}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[zone.scale.x, zone.scale.z]} />
        <meshBasicMaterial color={zone.color} transparent opacity={0.18} />
      </mesh>

      <lineSegments>
        <edgesGeometry
          args={[new THREE.BoxGeometry(zone.scale.x, 0.06, zone.scale.z)]}
        />
        <lineBasicMaterial color={zone.color} transparent opacity={0.55} />
      </lineSegments>
    </group>
  );
}

function SmokeSphere({ zone }: { zone: ZoneData }) {
  if (!zone.visible) return null;

  const radius = Math.max(zone.scale.x, zone.scale.y, zone.scale.z) / 2;

  return (
    <group position={zone.position.toArray() as Vec3}>
      <mesh>
        <sphereGeometry args={[radius, 32, 32]} />
        <meshStandardMaterial
          color={zone.color}
          transparent
          opacity={0.28}
          roughness={1}
          depthWrite={false}
        />
      </mesh>

      <mesh>
        <sphereGeometry args={[radius * 0.72, 24, 24]} />
        <meshStandardMaterial
          color={zone.color}
          transparent
          opacity={0.18}
          roughness={1}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

function CueMarker({ cue }: { cue: CueData }) {
  if (!cue.position) return null;

  return (
    <group position={cue.position.toArray() as Vec3}>
      <mesh>
        <sphereGeometry args={[0.32, 16, 16]} />
        <meshBasicMaterial color={cue.color} transparent opacity={0.85} />
      </mesh>

      <mesh position={[0, 0.65, 0]}>
        <torusGeometry args={[0.45, 0.035, 8, 32]} />
        <meshBasicMaterial color={cue.color} transparent opacity={0.65} />
      </mesh>
    </group>
  );
}

function GameLoop({
  callbacksRef,
  zonesRef,
  actionsRef,
  playerStateRef,
  movePlayerRequestRef,
  teleportPlayerRequestRef,
  locked,
  onMiss,
  onActionUsed,
  safeCall,
}: {
  callbacksRef: MutableRefObject<Callbacks>;
  zonesRef: MutableRefObject<Map<string, ZoneData>>;
  actionsRef: MutableRefObject<Map<string, ActionPromptData>>;
  playerStateRef: MutableRefObject<PlayerState>;
  movePlayerRequestRef: MutableRefObject<Vec3 | null>;
  teleportPlayerRequestRef: MutableRefObject<Vec3 | null>;
  locked: boolean;
  onMiss: () => void;
  onActionUsed: (id: string) => void;
  safeCall: SafeCall;
}) {
  const { camera, scene } = useThree();
  const raycasterRef = useRef(new THREE.Raycaster());
  const keysRef = useRef<Record<string, boolean>>({});

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      keysRef.current[e.key.toLowerCase()] = true;

      if (!locked) return;

      const pressed = e.key.toLowerCase();
      const prompt = Array.from(actionsRef.current.values()).find(
        action => action.key.toLowerCase() === pressed
      );

      if (!prompt) return;

      e.preventDefault();

      callbacksRef.current.action.get(prompt.id)?.forEach(cb => {
        safeCall(`onAction:${prompt.id}`, cb, prompt.id);
      });

      callbacksRef.current.anyAction.forEach(cb => {
        safeCall('onAnyAction', cb, prompt.id);
      });

      onActionUsed(prompt.id);

      if (prompt.removeOnUse) {
        actionsRef.current.delete(prompt.id);
      }
    }

    function onKeyUp(e: KeyboardEvent) {
      keysRef.current[e.key.toLowerCase()] = false;
    }

    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);

    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, [locked, actionsRef, callbacksRef, onActionUsed, safeCall]);

  useFrame((state, delta) => {
    const elapsed = state.clock.getElapsedTime();

    if (movePlayerRequestRef.current) {
      camera.position.add(new THREE.Vector3(...movePlayerRequestRef.current));
      camera.position.y = 1.6;
      movePlayerRequestRef.current = null;
    }

    if (teleportPlayerRequestRef.current) {
      camera.position.set(...teleportPlayerRequestRef.current);
      camera.position.y = 1.6;
      teleportPlayerRequestRef.current = null;
    }

    if (locked) {
      const speed = keysRef.current.shift ? 3.2 : 6.2;

      const forward = new THREE.Vector3();
      camera.getWorldDirection(forward);
      forward.y = 0;
      forward.normalize();

      const right = new THREE.Vector3()
        .crossVectors(forward, new THREE.Vector3(0, 1, 0))
        .normalize();

      const move = new THREE.Vector3();

      if (keysRef.current.w) move.add(forward);
      if (keysRef.current.s) move.sub(forward);
      if (keysRef.current.d) move.add(right);
      if (keysRef.current.a) move.sub(right);

      if (move.lengthSq() > 0) {
        move.normalize().multiplyScalar(speed * delta);
        camera.position.add(move);
        camera.position.x = THREE.MathUtils.clamp(camera.position.x, -70, 70);
        camera.position.z = THREE.MathUtils.clamp(camera.position.z, -75, 10);
        camera.position.y = 1.6;
      }
    }

    const direction = new THREE.Vector3();
    camera.getWorldDirection(direction);

    playerStateRef.current.position.copy(camera.position);
    playerStateRef.current.direction.copy(direction);

    zonesRef.current.forEach(zone => {
      const currentlyInside = inZone(camera.position, zone);
      const wasInside = playerStateRef.current.insideZones.has(zone.name);

      if (currentlyInside && !wasInside) {
        playerStateRef.current.insideZones.add(zone.name);

        callbacksRef.current.zoneEnter.get(zone.name)?.forEach(cb => {
          safeCall(`onZoneEnter:${zone.name}`, cb, zone.name);
        });
      }

      if (!currentlyInside && wasInside) {
        playerStateRef.current.insideZones.delete(zone.name);
      }
    });

    callbacksRef.current.tick.forEach(cb => {
      safeCall('onTick', cb, delta, elapsed);
    });
  });

  useEffect(() => {
    if (!locked) return;

    function shoot() {
      playerStateRef.current.lastShotAt = performance.now();

      raycasterRef.current.setFromCamera(new THREE.Vector2(0, 0), camera);

      const clickableObjects: THREE.Object3D[] = [];

      scene.traverse(obj => {
        if ((obj as THREE.Mesh).isMesh && obj.userData.sandboxClickable) {
          clickableObjects.push(obj);
        }
      });

      const hits = raycasterRef.current.intersectObjects(clickableObjects, false);

      if (hits.length > 0) {
        const hitObj = hits[0].object;

        try {
          if (hitObj.userData.sandboxKind === 'enemy') {
            hitObj.userData.triggerEnemyHit?.();
            return;
          }

          hitObj.userData.triggerHit?.();
          return;
        } catch (err) {
          console.error('[Drill click handler error]', err);
          return;
        }
      }

      onMiss();
    }

    window.addEventListener('click', shoot);

    return () => {
      window.removeEventListener('click', shoot);
    };
  }, [locked, camera, scene, onMiss, playerStateRef]);

  return null;
}

export function DrillSandbox({ config, onComplete }: Props) {
  const theme = getTheme(config.map_theme ?? 'default');
  const activeArena = getArenaPreset(config.arena_preset);

  const [locked, setLocked] = useState(false);
  const [started, setStarted] = useState(false);
  const [finished, setFinished] = useState(false);
  const [hud, setHUDState] = useState<SandboxHUD>({});
  const [scriptError, setScriptError] = useState<string | null>(null);
  const [renderTick, setRenderTick] = useState(0);
  const [misses, setMisses] = useState(0);
  const [completionStats, setCompletionStats] = useState<CompletionStats | null>(null);

  const [objective, setObjectiveState] = useState<ObjectiveData>({
    requiredActions: [],
    completedActions: [],
  });

  const targetsRef = useRef<Map<string, TargetData>>(new Map());
  const enemiesRef = useRef<Map<string, EnemyData>>(new Map());
  const coverRef = useRef<Map<string, CoverData>>(new Map());
  const zonesRef = useRef<Map<string, ZoneData>>(new Map());
  const cuesRef = useRef<Map<string, CueData>>(new Map());
  const actionsRef = useRef<Map<string, ActionPromptData>>(new Map());
  const abilityBindingsRef = useRef<Map<string, AbilityBindingData>>(new Map());

  const movePlayerRequestRef = useRef<Vec3 | null>(null);
  const teleportPlayerRequestRef = useRef<Vec3 | null>(null);

  const playerStateRef = useRef<PlayerState>({
    position: new THREE.Vector3(...activeArena.spawn),
    direction: new THREE.Vector3(0, 0, -1),
    insideZones: new Set(),
    lastShotAt: 0,
  });

  const callbacksRef = useRef<Callbacks>({
    hit: new Map(),
    anyHit: [],
    enemyHit: new Map(),
    anyEnemyHit: [],
    miss: [],
    tick: [],
    action: new Map(),
    anyAction: [],
    zoneEnter: new Map(),
    timers: [],
    intervals: [],
  });

  const completedRef = useRef(false);

  const safeCall = useCallback<SafeCall>((label, cb, ...args) => {
    try {
      cb(...args);
    } catch (err: unknown) {
      console.error(`[Drill script callback error: ${label}]`, err);

      const message =
        err instanceof Error
          ? err.message
          : `Script callback failed: ${label}`;

      setScriptError(message);
    }
  }, []);

  function rerender() {
    setRenderTick(t => t + 1);
  }

  const complete = useCallback(
    (stats: CompletionStats = {}) => {
      if (completedRef.current) return;

      completedRef.current = true;
      setCompletionStats(stats);
      setFinished(true);

      callbacksRef.current.timers.forEach(clearTimeout);
      callbacksRef.current.intervals.forEach(clearInterval);

      onComplete(stats);
    },
    [onComplete]
  );

  const markActionComplete = useCallback((id: string) => {
    setObjectiveState(prev => {
      if (prev.completedActions.includes(id)) return prev;

      return {
        ...prev,
        completedActions: [...prev.completedActions, id],
      };
    });

    rerender();
  }, []);

  const spawnTargetInternal = useCallback((opts: Partial<SpawnOpts> = {}): string => {
    const id = makeId('t_');
    const position = safeVec3(opts.position, [0, 1.6, -15]);

    targetsRef.current.set(id, {
      id,
      position: new THREE.Vector3(...position),
      size: safeNumber(opts.size, 0.26),
      color: opts.color ?? '#ff4655',
      velocity: opts.velocity
        ? new THREE.Vector3(...safeVec3(opts.velocity, [0, 0, 0]))
        : undefined,
      bounds: safeBounds(opts.bounds),
      label: opts.label,
    });

    rerender();
    return id;
  }, []);

  const spawnEnemyInternal = useCallback((opts: Partial<EnemyOpts> = {}): string => {
    const id = makeId('e_');

    const position = safeVec3(opts.position, [0, 0, -14]);
    const start = safeVec3(opts.hiddenPosition, position);
    const behavior = opts.behavior ?? 'hold_angle';

    enemiesRef.current.set(id, {
      id,
      position: new THREE.Vector3(...start),
      basePosition: new THREE.Vector3(...start),
      targetPosition: opts.swingTo
        ? new THREE.Vector3(...safeVec3(opts.swingTo, position))
        : behavior === 'swing'
          ? new THREE.Vector3(...position)
          : undefined,
      velocity: opts.velocity
        ? new THREE.Vector3(...safeVec3(opts.velocity, [0, 0, 0]))
        : undefined,
      bounds: safeBounds(opts.bounds),
      behavior,
      size: safeNumber(opts.size, 1.05),
      color: opts.color ?? (behavior === 'decoy' ? '#888888' : '#ff4655'),
      label: opts.label ?? 'enemy',
      hp: safeNumber(opts.hp, 1),
      maxHp: safeNumber(opts.hp, 1),
      reactionMs: safeNumber(opts.reactionMs, 650),
      weapon: opts.weapon,
      alive: true,
      jiggleAxis: 'x',
      jiggleAmount: 0.9,
      jiggleSpeed: 4,
      moveSpeed: safeNumber(opts.swingSpeed, 6),
    });

    rerender();
    return id;
  }, []);

  const spawnCoverInternal = useCallback((opts: Partial<CoverOpts> = {}): string => {
    const id = makeId('c_');

    coverRef.current.set(id, {
      id,
      position: new THREE.Vector3(...safeVec3(opts.position, [0, 1.25, -12])),
      scale: new THREE.Vector3(...safeVec3(opts.scale, [2, 2.5, 0.8])),
      color: opts.color ?? '#3a3a3a',
      label: opts.label,
    });

    rerender();
    return id;
  }, []);

  const createZoneInternal = useCallback((opts: Partial<ZoneOpts> = {}): string => {
    const id = makeId('z_');

    zonesRef.current.set(id, {
      id,
      name: opts.name ?? id,
      position: new THREE.Vector3(...safeVec3(opts.position, [0, 0.05, -15])),
      scale: new THREE.Vector3(...safeVec3(opts.scale, [4, 2, 4])),
      color: opts.color ?? '#1dc8a0',
      visible: opts.visible ?? true,
      label: opts.label,
      shape: opts.shape ?? 'box',
    });

    rerender();
    return id;
  }, []);

  const removeZoneInternal = useCallback((idOrName: string) => {
    if (zonesRef.current.has(idOrName)) {
      zonesRef.current.delete(idOrName);
      rerender();
      return;
    }

    Array.from(zonesRef.current.entries()).forEach(([id, zone]) => {
      if (zone.name === idOrName) {
        zonesRef.current.delete(id);
      }
    });

    rerender();
  }, []);

  const emitCueInternal = useCallback((opts: Partial<CueOpts> = {}): string => {
    const id = makeId('cue_');

    cuesRef.current.set(id, {
      id,
      type: opts.type ?? 'info',
      message: opts.message ?? 'Cue',
      position: opts.position
        ? new THREE.Vector3(...safeVec3(opts.position, [0, 1.6, -10]))
        : undefined,
      color: opts.color ?? '#ffd166',
    });

    rerender();

    const timer = setTimeout(() => {
      cuesRef.current.delete(id);
      rerender();
    }, safeNumber(opts.durationMs, 1800));

    callbacksRef.current.timers.push(timer);

    return id;
  }, []);

  const clearCueInternal = useCallback((id: string) => {
    cuesRef.current.delete(id);
    rerender();
  }, []);

  const afterInternal = useCallback(
    (ms: number, cb: () => void, label = 'after') => {
      const timer = setTimeout(() => {
        safeCall(label, cb);
      }, ms);

      callbacksRef.current.timers.push(timer);
      return timer as unknown as number;
    },
    [safeCall]
  );

  const everyInternal = useCallback(
    (ms: number, cb: () => void, label = 'every') => {
      const id = setInterval(() => {
        safeCall(label, cb);
      }, ms) as unknown as number;

      callbacksRef.current.intervals.push(
        id as unknown as ReturnType<typeof setInterval>
      );

      return id;
    },
    [safeCall]
  );

  const useAbilityInternal = useCallback(
    (abilityId: string, opts: Record<string, unknown> = {}) => {
      const ability = getAbilityById(abilityId);

      if (!ability) {
        throw new Error(`Unknown ability: ${abilityId}`);
      }

      const player = playerStateRef.current;

      ability.use(
        {
          movePlayerBy(delta: Vec3) {
            movePlayerRequestRef.current = safeVec3(delta, [0, 0, 0]);
          },

          teleportPlayer(position: Vec3) {
            teleportPlayerRequestRef.current = safeVec3(position, activeArena.spawn);
          },

          emitCue: emitCueInternal as any,
          createZone: createZoneInternal as any,
          removeZone: removeZoneInternal,
          spawnCover: spawnCoverInternal as any,
          spawnEnemy: spawnEnemyInternal as any,

          swingEnemy(id: string, to: Vec3, speed = 7) {
            const enemy = enemiesRef.current.get(id);
            if (!enemy) return;

            enemy.behavior = 'swing';
            enemy.targetPosition = new THREE.Vector3(...safeVec3(to, [0, 0, -12]));
            enemy.moveSpeed = speed;
            rerender();
          },

          fallBackEnemy(id: string, to: Vec3, speed = 5) {
            const enemy = enemiesRef.current.get(id);
            if (!enemy) return;

            enemy.behavior = 'fall_back';
            enemy.targetPosition = new THREE.Vector3(...safeVec3(to, [0, 0, -12]));
            enemy.moveSpeed = speed;
            rerender();
          },

          setHUD(opts: HUDOpts) {
            setHUDState(prev => ({ ...prev, ...opts }));
          },

          after(ms: number, cb: () => void) {
            return afterInternal(ms, cb, `ability:${abilityId}:after`);
          },
        },
        opts,
        {
          playerPosition: toVec3(player.position),
          playerDirection: toVec3(player.direction),
          now: performance.now(),
        }
      );
    },
    [
      activeArena.spawn,
      afterInternal,
      createZoneInternal,
      emitCueInternal,
      removeZoneInternal,
      spawnCoverInternal,
      spawnEnemyInternal,
    ]
  );

  const handleActionUsed = useCallback(
    (id: string) => {
      const binding = abilityBindingsRef.current.get(id);

      if (binding) {
        safeCall(
          `useAbility:${binding.abilityId}`,
          () => useAbilityInternal(binding.abilityId, binding.options)
        );
      }

      markActionComplete(id);
    },
    [markActionComplete, safeCall, useAbilityInternal]
  );

  const drillAPI = useMemo(
    () => ({
      spawn(opts: Partial<SpawnOpts> = {}) {
        return spawnTargetInternal(opts);
      },

      despawn(id: string) {
        targetsRef.current.delete(id);
        callbacksRef.current.hit.delete(id);
        rerender();
      },

      spawnEnemy(opts: Partial<EnemyOpts> = {}) {
        return spawnEnemyInternal(opts);
      },

      spawnEnemyAt(pointId: string, opts: Partial<EnemyOpts> = {}) {
        const position = resolveArenaPoint(config.arena_preset, pointId, [0, 0, -14]);
        return spawnEnemyInternal({ ...opts, position });
      },

      despawnEnemy(id: string) {
        enemiesRef.current.delete(id);
        callbacksRef.current.enemyHit.delete(id);
        rerender();
      },

      spawnCover(opts: Partial<CoverOpts> = {}) {
        return spawnCoverInternal(opts);
      },

      spawnCoverAt(pointId: string, opts: Partial<CoverOpts> = {}) {
        const position = resolveArenaPoint(config.arena_preset, pointId, [0, 1.25, -12]);
        return spawnCoverInternal({ ...opts, position });
      },

      createZone(opts: Partial<ZoneOpts> = {}) {
        return createZoneInternal(opts);
      },

      createZoneAt(pointId: string, opts: Partial<ZoneOpts> = {}) {
        const position = resolveArenaPoint(config.arena_preset, pointId, [0, 0.05, -15]);
        return createZoneInternal({ ...opts, position });
      },

      removeZone(idOrName: string) {
        removeZoneInternal(idOrName);
      },

      emitCue(opts: Partial<CueOpts> = {}) {
        return emitCueInternal(opts);
      },

      emitCueAt(pointId: string, opts: Partial<CueOpts> = {}) {
        const position = resolveArenaPoint(config.arena_preset, pointId, [0, 1.6, -10]);
        return emitCueInternal({ ...opts, position });
      },

      clearCue(id: string) {
        clearCueInternal(id);
      },

      useAbility(abilityId: string, opts: Record<string, unknown> = {}) {
        useAbilityInternal(abilityId, opts);
      },

      useAbilityAt(abilityId: string, pointId: string, opts: Record<string, unknown> = {}) {
        const position = resolveArenaPoint(config.arena_preset, pointId, [0, 1.6, -12]);
        useAbilityInternal(abilityId, { ...opts, position });
      },

      bindAbility(opts: AbilityBindOpts): string {
        const ability = getAbilityById(opts.abilityId);

        if (!ability) {
          throw new Error(`Cannot bind unknown ability: ${opts.abilityId}`);
        }

        const id = opts.id ?? opts.abilityId;

        actionsRef.current.set(id, {
          id,
          key: opts.key.toLowerCase(),
          label: opts.label ?? ability.name,
          hint: opts.hint ?? ability.description,
          removeOnUse: opts.removeOnUse ?? false,
        });

        abilityBindingsRef.current.set(id, {
          actionId: id,
          abilityId: opts.abilityId,
          options: opts.options ?? {},
        });

        rerender();

        if (opts.expiresMs) {
          const timer = setTimeout(() => {
            actionsRef.current.delete(id);
            abilityBindingsRef.current.delete(id);
            rerender();
          }, opts.expiresMs);

          callbacksRef.current.timers.push(timer);
        }

        return id;
      },

      setPlayerSpawn(pointId: string) {
        teleportPlayerRequestRef.current = resolveArenaPoint(
          config.arena_preset,
          pointId,
          activeArena.spawn
        );
      },

      resolvePoint(pointId: string) {
        return resolveArenaPoint(config.arena_preset, pointId, [0, 1.6, -12]);
      },

      getArenaPreset() {
        return {
          id: activeArena.id,
          label: activeArena.label,
          description: activeArena.description,
          points: Object.values(activeArena.points).map(point => ({
            id: point.id,
            label: point.label,
            position: point.position,
          })),
        };
      },

      setPosition(id: string, position: Vec3) {
        const safe = safeVec3(position, [0, 1.6, -12]);
        const target = targetsRef.current.get(id);
        const enemy = enemiesRef.current.get(id);

        if (target) {
          target.position.set(...safe);
          rerender();
          return;
        }

        if (enemy) {
          enemy.position.set(...safe);
          enemy.basePosition.set(...safe);
          rerender();
        }
      },

      setVelocity(id: string, velocity: Vec3) {
        const safe = safeVec3(velocity, [0, 0, 0]);
        const target = targetsRef.current.get(id);
        const enemy = enemiesRef.current.get(id);

        if (target) target.velocity = new THREE.Vector3(...safe);
        if (enemy) enemy.velocity = new THREE.Vector3(...safe);
      },

      setColor(id: string, color: string) {
        const target = targetsRef.current.get(id);
        const enemy = enemiesRef.current.get(id);

        if (target) {
          target.color = color;
          rerender();
          return;
        }

        if (enemy) {
          enemy.color = color;
          rerender();
        }
      },

      swingEnemy(id: string, to: Vec3, speed = 7) {
        const enemy = enemiesRef.current.get(id);
        if (!enemy) return;

        enemy.behavior = 'swing';
        enemy.targetPosition = new THREE.Vector3(...safeVec3(to, [0, 0, -12]));
        enemy.moveSpeed = speed;
        rerender();
      },

      fallBackEnemy(id: string, to: Vec3, speed = 5) {
        const enemy = enemiesRef.current.get(id);
        if (!enemy) return;

        enemy.behavior = 'fall_back';
        enemy.targetPosition = new THREE.Vector3(...safeVec3(to, [0, 0, -12]));
        enemy.moveSpeed = speed;
        rerender();
      },

      jiggleEnemy(id: string, axis: Axis = 'x', amount = 1.1, speed = 5) {
        const enemy = enemiesRef.current.get(id);
        if (!enemy) return;

        enemy.behavior = 'jiggle';
        enemy.basePosition.copy(enemy.position);
        enemy.jiggleAxis = axis;
        enemy.jiggleAmount = amount;
        enemy.jiggleSpeed = speed;
        rerender();
      },

      holdEnemy(id: string) {
        const enemy = enemiesRef.current.get(id);
        if (!enemy) return;

        enemy.behavior = 'hold_angle';
        enemy.targetPosition = undefined;
        enemy.velocity = undefined;
        rerender();
      },

      setObjective(opts: ObjectiveOpts) {
        setObjectiveState({
          title: opts.title,
          details: opts.details,
          requiredActions: opts.requiredActions ?? [],
          completedActions: [],
        });
      },

      addActionPrompt(opts: ActionPromptOpts): string {
        const id = opts.id ?? makeId('act_');

        actionsRef.current.set(id, {
          id,
          key: opts.key.toLowerCase(),
          label: opts.label,
          hint: opts.hint,
          removeOnUse: opts.removeOnUse ?? true,
        });

        rerender();

        if (opts.expiresMs) {
          const timer = setTimeout(() => {
            actionsRef.current.delete(id);
            abilityBindingsRef.current.delete(id);
            rerender();
          }, opts.expiresMs);

          callbacksRef.current.timers.push(timer);
        }

        return id;
      },

      removeActionPrompt(id: string) {
        actionsRef.current.delete(id);
        abilityBindingsRef.current.delete(id);
        rerender();
      },

      markActionComplete(id: string) {
        markActionComplete(id);
      },

      onAction(id: string, cb: (id: string) => void) {
        const list = callbacksRef.current.action.get(id) ?? [];
        list.push(cb);
        callbacksRef.current.action.set(id, list);
      },

      onAnyAction(cb: (id: string) => void) {
        callbacksRef.current.anyAction.push(cb);
      },

      onZoneEnter(zoneName: string, cb: (zoneName: string) => void) {
        const list = callbacksRef.current.zoneEnter.get(zoneName) ?? [];
        list.push(cb);
        callbacksRef.current.zoneEnter.set(zoneName, list);
      },

      onHit(id: string, cb: (id: string) => void) {
        callbacksRef.current.hit.set(id, cb);
      },

      onAnyHit(cb: (id: string) => void) {
        callbacksRef.current.anyHit.push(cb);
      },

      onEnemyHit(id: string, cb: (id: string) => void) {
        callbacksRef.current.enemyHit.set(id, cb);
      },

      onAnyEnemyHit(cb: (id: string) => void) {
        callbacksRef.current.anyEnemyHit.push(cb);
      },

      onMiss(cb: () => void) {
        callbacksRef.current.miss.push(cb);
      },

      onTick(cb: (dt: number, elapsed: number) => void) {
        callbacksRef.current.tick.push(cb);
      },

      setHUD(opts: HUDOpts) {
        setHUDState(prev => ({ ...prev, ...opts }));
      },

      after(ms: number, cb: () => void) {
        return afterInternal(ms, cb, 'Drill.after');
      },

      every(ms: number, cb: () => void): number {
        return everyInternal(ms, cb, 'Drill.every');
      },

      clearTimer(id: number) {
        clearInterval(id as unknown as ReturnType<typeof setInterval>);
        clearTimeout(id as unknown as ReturnType<typeof setTimeout>);
      },

      getPlayerState() {
        const player = playerStateRef.current;

        return {
          position: toVec3(player.position),
          direction: toVec3(player.direction),
          insideZones: Array.from(player.insideZones),
          lastShotAt: player.lastShotAt,
        };
      },

      getTargetIds(): string[] {
        return Array.from(targetsRef.current.keys());
      },

      getEnemyIds(): string[] {
        return Array.from(enemiesRef.current.keys());
      },

      targetCount(): number {
        return targetsRef.current.size;
      },

      enemyCount(): number {
        return Array.from(enemiesRef.current.values()).filter(enemy => enemy.alive)
          .length;
      },

      complete,

      random(min: number, max: number) {
        return Math.random() * (max - min) + min;
      },

      randomInt(min: number, max: number) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
      },

      lerp(a: number, b: number, t: number) {
        return a + (b - a) * t;
      },
    }),
    [
      activeArena,
      afterInternal,
      clearCueInternal,
      complete,
      config.arena_preset,
      createZoneInternal,
      emitCueInternal,
      everyInternal,
      markActionComplete,
      removeZoneInternal,
      spawnCoverInternal,
      spawnEnemyInternal,
      spawnTargetInternal,
      useAbilityInternal,
    ]
  );

  useEffect(() => {
    if (!started || scriptError) return;

    try {
      // eslint-disable-next-line no-new-func
      const fn = new Function('Drill', 'console', 'Math', config.drill_script);
      fn(drillAPI, console, Math);
    } catch (err: unknown) {
      console.error('Drill script error:', err);

      const message =
        err instanceof Error ? err.message : 'Unknown drill script error';

      setScriptError(message);
    }

    return () => {
      callbacksRef.current.timers.forEach(clearTimeout);
      callbacksRef.current.intervals.forEach(clearInterval);

      targetsRef.current.clear();
      enemiesRef.current.clear();
      coverRef.current.clear();
      zonesRef.current.clear();
      cuesRef.current.clear();
      actionsRef.current.clear();
      abilityBindingsRef.current.clear();

      callbacksRef.current.hit.clear();
      callbacksRef.current.anyHit = [];
      callbacksRef.current.enemyHit.clear();
      callbacksRef.current.anyEnemyHit = [];
      callbacksRef.current.miss = [];
      callbacksRef.current.tick = [];
      callbacksRef.current.action.clear();
      callbacksRef.current.anyAction = [];
      callbacksRef.current.zoneEnter.clear();
    };
  }, [started, scriptError, config.drill_script, drillAPI]);

  const handleMiss = useCallback(() => {
    setMisses(m => m + 1);

    callbacksRef.current.miss.forEach(cb => {
      safeCall('onMiss', cb);
    });
  }, [safeCall]);

  const targetIds = Array.from(targetsRef.current.keys());
  const enemyIds = Array.from(enemiesRef.current.keys());
  const covers = Array.from(coverRef.current.values());
  const zones = Array.from(zonesRef.current.values());
  const cues = Array.from(cuesRef.current.values());
  const actionPrompts = Array.from(actionsRef.current.values());

  void renderTick;

  if (finished) {
    return (
      <div className="sandbox__done">
        <div className="sandbox__done-panel">
          <span className="label">{config.drill_name}</span>

          <h2>
            {completionStats?.passed === false ? 'Try Again' : 'Drill Complete'}
          </h2>

          {completionStats?.message && (
            <p className="sandbox__done-msg">
              {completionStats.message as string}
            </p>
          )}

          {completionStats?.score != null && (
            <div className="sandbox__done-score mono">
              {completionStats.score as number}
            </div>
          )}

          {completionStats?.passed !== undefined && (
            <div
              className={`sandbox__done-verdict ${
                completionStats.passed
                  ? 'sandbox__done-verdict--pass'
                  : 'sandbox__done-verdict--fail'
              }`}
            >
              {completionStats.passed ? '✓ Passed' : '✗ Failed'}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="sandbox">
      {!started && (
        <div className="sandbox__overlay">
          <div className="sandbox__overlay-panel">
            <span className="label">
              {config.arena_preset?.replace(/_/g, ' ') ?? 'training arena'}
            </span>

            <h2>{config.drill_name}</h2>

            <p className="sandbox__overlay-desc">{config.drill_instructions}</p>

            <div className="sandbox__hint-click">
              Click to lock cursor and begin
            </div>
          </div>
        </div>
      )}

      {scriptError && (
        <div className="sandbox__error">
          <span className="label">Drill script error</span>
          <p className="mono">{scriptError}</p>
        </div>
      )}

      {started && !scriptError && (
        <div className="sandbox__hud sandbox__hud--scenario">
          {hud.score != null && (
            <div className="sandbox__hud-stat">
              <span className="label">Score</span>
              <span
                className="mono"
                style={{ fontSize: '22px', color: 'var(--teal)' }}
              >
                {hud.score}
              </span>
            </div>
          )}

          {hud.timeLeft != null && (
            <div className="sandbox__hud-stat">
              <span className="label">Time</span>
              <span className="mono" style={{ fontSize: '22px' }}>
                {hud.timeLeft}
              </span>
            </div>
          )}

          {hud.message && (
            <div className="sandbox__hud-message">{hud.message}</div>
          )}

          {misses > 0 && (
            <div className="sandbox__hud-stat">
              <span className="label">Misses</span>
              <span
                className="mono"
                style={{ fontSize: '22px', color: 'var(--red)' }}
              >
                {misses}
              </span>
            </div>
          )}
        </div>
      )}

      {started && (objective.title || objective.details) && (
        <div className="sandbox__objective">
          {objective.title && (
            <div className="sandbox__objective-title">{objective.title}</div>
          )}

          {objective.details && (
            <div className="sandbox__objective-details">
              {objective.details}
            </div>
          )}

          {objective.requiredActions.length > 0 && (
            <div className="sandbox__objective-actions">
              {objective.requiredActions.map(action => (
                <span
                  key={action}
                  className={
                    objective.completedActions.includes(action) ? 'done' : ''
                  }
                >
                  {action}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {started && cues.length > 0 && (
        <div className="sandbox__cues">
          {cues.slice(-4).map(cue => (
            <div
              key={cue.id}
              className={`sandbox__cue sandbox__cue--${cue.type}`}
            >
              {cue.message}
            </div>
          ))}
        </div>
      )}

      {started && actionPrompts.length > 0 && (
        <div className="sandbox__actions">
          {actionPrompts.map(action => (
            <div key={action.id} className="sandbox__action">
              <kbd>{action.key.toUpperCase()}</kbd>
              <span>{action.label}</span>
              {action.hint && <small>{action.hint}</small>}
            </div>
          ))}
        </div>
      )}

      {started && hud.hint && <div className="sandbox__hint">{hud.hint}</div>}

      {locked && (
        <div className="sandbox__crosshair" aria-hidden>
          <div className="sandbox__ch-h" />
          <div className="sandbox__ch-v" />
          <div className="sandbox__ch-dot" />
        </div>
      )}

      {locked && (
        <div className="sandbox__esc">
          WASD move • Shift walk • Click shoot • ESC exit
        </div>
      )}

      <Canvas
        shadows
        gl={{ antialias: true }}
        camera={{ position: activeArena.spawn, fov: 75 }}
        onPointerDown={() => {
          if (!started) setStarted(true);
        }}
      >
        <fog attach="fog" args={[theme.fog, 28, 100]} />

        <ambientLight intensity={theme.ambient} />

        <directionalLight
          position={[8, 18, 4]}
          intensity={1.1}
          castShadow
          shadow-mapSize={[2048, 2048]}
        />

        <Sky
          turbidity={theme.sky[0]}
          rayleigh={theme.sky[1]}
          mieCoefficient={theme.sky[2]}
          mieDirectionalG={theme.sky[3]}
          sunPosition={[0.5, theme.sky[4], 0]}
        />

        <TrainingArena
          arenaId={config.arena_preset}
          groundColor={theme.ground}
        />

        {covers.map(cover => (
          <CoverMesh key={cover.id} cover={cover} />
        ))}

        {zones.map(zone =>
          zone.shape === 'sphere' ? (
            <SmokeSphere key={zone.id} zone={zone} />
          ) : (
            <ZoneMesh key={zone.id} zone={zone} />
          )
        )}

        {cues.map(cue => (
          <CueMarker key={cue.id} cue={cue} />
        ))}

        {targetIds.map(id => (
          <SandboxTargetMesh
            key={id}
            id={id}
            targetsRef={targetsRef}
            callbacksRef={callbacksRef}
            safeCall={safeCall}
          />
        ))}

        {enemyIds.map(id => (
          <EnemyMesh
            key={id}
            id={id}
            enemiesRef={enemiesRef}
            callbacksRef={callbacksRef}
            safeCall={safeCall}
            rerender={rerender}
          />
        ))}

        <GameLoop
          callbacksRef={callbacksRef}
          zonesRef={zonesRef}
          actionsRef={actionsRef}
          playerStateRef={playerStateRef}
          movePlayerRequestRef={movePlayerRequestRef}
          teleportPlayerRequestRef={teleportPlayerRequestRef}
          locked={locked}
          onMiss={handleMiss}
          onActionUsed={handleActionUsed}
          safeCall={safeCall}
        />

        <PointerLockControls
          onLock={() => setLocked(true)}
          onUnlock={() => setLocked(false)}
        />
      </Canvas>
    </div>
  );
}