"use client";

import { useRef, useMemo, useCallback, useState, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { CameraControls } from "@react-three/drei";
import * as THREE from "three";
import type { SongPoint } from "../lib/api";

// ---------------------------------------------------------------------------
// Colors
// ---------------------------------------------------------------------------

const COLOR_GLOBAL = new THREE.Color("#4a4a5a");
const COLOR_USER = new THREE.Color("#1DB954");
const COLOR_NEIGHBOR = new THREE.Color("#FF6B35");
const COLOR_WALK = new THREE.Color("#A855F7");
const COLOR_CURRENT = new THREE.Color("#FF2D2D");

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface PointCloudViewerProps {
  globalPoints: SongPoint[];
  userSongIds: Set<string>;
  neighborIds: Set<string>;
  walkIds: Set<string>;
  walkActive?: boolean;
  walkPathIds?: string[];
  walkProgress?: number;
  coordMode: "raw" | "uniform";
  onPointClick: (point: SongPoint) => void;
  selectedId?: string | null;
}

function getShiftedCoords(point: SongPoint, coordMode: "raw" | "uniform"): [number, number, number] | null {
  const xyz = coordMode === "raw" ? point.xyz_raw : point.xyz_uniform;
  if (!Array.isArray(xyz) || xyz.length < 3) return null;

  const x = Number(xyz[0]);
  const y = Number(xyz[1]);
  const z = Number(xyz[2]);
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) return null;

  return [x - 0.5, y - 0.5, z - 0.5];
}

function WalkPathOverlay({
  globalPoints,
  walkPathIds,
  walkProgress = 0,
  coordMode,
}: {
  globalPoints: SongPoint[];
  walkPathIds?: string[];
  walkProgress?: number;
  coordMode: "raw" | "uniform";
}) {
  const lineRef = useRef<any>(null);
  const headRef = useRef<THREE.Mesh>(null);
  const nextRef = useRef<THREE.Mesh>(null);
  const nextGlowRef = useRef<THREE.Mesh>(null);
  const arrowRef = useRef<THREE.Mesh>(null);

  const byId = useMemo(() => new Map(globalPoints.map((p) => [p.track_id, p])), [globalPoints]);

  const toVec3 = useCallback((song: SongPoint) => {
    const shifted = getShiftedCoords(song, coordMode);
    if (!shifted) return null;
    return new THREE.Vector3(shifted[0], shifted[1], shifted[2]);
  }, [coordMode]);

  const safeIndex = Math.max(0, walkProgress ?? 0);
  const currentId = walkPathIds && walkPathIds.length > 0
    ? walkPathIds[Math.min(safeIndex, walkPathIds.length - 1)] ?? null
    : null;
  const nextId = walkPathIds && walkPathIds.length > safeIndex + 1
    ? walkPathIds[safeIndex + 1] ?? null
    : null;

  const currentPoint = currentId ? byId.get(currentId) ?? null : null;
  const nextPointSong = nextId ? byId.get(nextId) ?? null : null;
  const currentPointVec = currentPoint ? toVec3(currentPoint) : null;
  const nextPointVec = nextPointSong ? toVec3(nextPointSong) : null;

  const orderedPoints = useMemo(() => {
    if (!walkPathIds || walkPathIds.length < 2) return [] as THREE.Vector3[];
    return walkPathIds
      .map((id) => byId.get(id))
      .filter((p): p is SongPoint => !!p)
      .map((p) => toVec3(p))
      .filter((p): p is THREE.Vector3 => !!p);
  }, [walkPathIds, byId, toVec3]);

  const visibleCount = Math.min(orderedPoints.length, Math.max(1, walkProgress + 1));
  const visiblePoints = useMemo(() => orderedPoints.slice(0, visibleCount), [orderedPoints, visibleCount]);

  useEffect(() => {
    if (lineRef.current) {
      lineRef.current.computeLineDistances();
    }
  }, [visiblePoints]);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (lineRef.current) {
      const material = lineRef.current.material as any;
      material.dashOffset = -t * 0.8;
    }

    if (headRef.current && currentPointVec) {
      headRef.current.position.copy(currentPointVec);
      const pulse = 1 + 0.22 * (0.5 + 0.5 * Math.sin(t * 6));
      headRef.current.scale.setScalar(pulse);
    }

    if (nextRef.current && nextPointVec) {
      nextRef.current.position.copy(nextPointVec);
      const pulse = 1 + 0.22 * (0.5 + 0.5 * Math.sin(t * 5.2));
      nextRef.current.scale.setScalar(pulse);
    }

    if (nextGlowRef.current && nextPointVec) {
      nextGlowRef.current.position.copy(nextPointVec);
      const glowPulse = 1 + 0.3 * (0.5 + 0.5 * Math.sin(t * 4.1));
      nextGlowRef.current.scale.setScalar(glowPulse);
    }

    if (arrowRef.current && currentPointVec && nextPointVec) {
      const dir = new THREE.Vector3().subVectors(nextPointVec, currentPointVec).normalize();
      const arrowPos = new THREE.Vector3().copy(nextPointVec).addScaledVector(dir, -0.0075);
      arrowRef.current.position.copy(arrowPos);
      arrowRef.current.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
      const arrowPulse = 1 + 0.12 * (0.5 + 0.5 * Math.sin(t * 7));
      arrowRef.current.scale.setScalar(arrowPulse);
      arrowRef.current.visible = true;
    } else if (arrowRef.current) {
      arrowRef.current.visible = false;
    }
  });

  if (visiblePoints.length < 2) return null;

  const linePositions = new Float32Array(visiblePoints.length * 3);
  visiblePoints.forEach((p, i) => {
    linePositions[i * 3] = p.x;
    linePositions[i * 3 + 1] = p.y;
    linePositions[i * 3 + 2] = p.z;
  });

  return (
    <group>
      <line ref={lineRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[linePositions, 3]} />
        </bufferGeometry>
        <lineDashedMaterial
          color="#A855F7"
          linewidth={1}
          dashSize={0.03}
          gapSize={0.018}
          transparent
          opacity={0.9}
        />
      </line>

      <mesh ref={headRef}>
        <sphereGeometry args={[0.0085, 16, 16]} />
        <meshBasicMaterial color="#FF2D2D" transparent opacity={1} />
      </mesh>

      {nextPointVec && (
        <>
          <mesh ref={nextRef}>
            <sphereGeometry args={[0.0076, 16, 16]} />
            <meshBasicMaterial color="#A855F7" transparent opacity={0.98} />
          </mesh>
          <mesh ref={nextGlowRef}>
            <sphereGeometry args={[0.0128, 16, 16]} />
            <meshBasicMaterial color="#C084FC" transparent opacity={0.28} />
          </mesh>
        </>
      )}

      <mesh ref={arrowRef}>
        <coneGeometry args={[0.0055, 0.015, 12]} />
        <meshBasicMaterial color="#FFC7C7" transparent opacity={0.72} />
      </mesh>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Circle texture — renders points as filled circles via alphaTest
// ---------------------------------------------------------------------------

function makeCircleTexture(): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext("2d")!;
  ctx.beginPath();
  ctx.arc(32, 32, 30, 0, Math.PI * 2);
  ctx.fillStyle = "white";
  ctx.fill();
  return new THREE.CanvasTexture(canvas);
}

// ---------------------------------------------------------------------------
// Auto-rotate — nudges azimuth each frame, pauses while user interacts
// ---------------------------------------------------------------------------

function AutoRotate({
  controlsRef,
  isInteracting,
}: {
  controlsRef: React.RefObject<CameraControls>;
  isInteracting: React.RefObject<boolean>;
}) {
  useFrame((_, delta) => {
    if (!isInteracting.current && controlsRef.current) {
      controlsRef.current.azimuthAngle += 0.06 * delta;
    }
  });
  return null;
}

// ---------------------------------------------------------------------------
// Inner scene — must live inside <Canvas>
// ---------------------------------------------------------------------------

function PointCloud({
  globalPoints,
  userSongIds,
  neighborIds,
  walkIds,
  walkActive,
  walkPathIds,
  walkProgress,
  selectedId,
  coordMode,
  onHover,
  mouseNDC,
  hoveredRef,
}: Omit<PointCloudViewerProps, "onPointClick"> & {
  onHover: (point: SongPoint | null) => void;
  mouseNDC: React.RefObject<{ x: number; y: number } | null>;
  hoveredRef: React.MutableRefObject<SongPoint | null>;
}) {
  const meshRef = useRef<THREE.Points>(null);
  const { camera, size } = useThree();
  const tempVec = useMemo(() => new THREE.Vector3(), []);
  const circleTexture = useMemo(() => makeCircleTexture(), []);
  const walkCurrentId = useMemo(() => {
    if (!walkPathIds || walkPathIds.length === 0) return null;
    const idx = Math.max(0, Math.min(walkPathIds.length - 1, walkProgress ?? 0));
    return walkPathIds[idx] ?? null;
  }, [walkPathIds, walkProgress]);
  const selectedPoint = useMemo(() => {
    if (!selectedId) return null;
    return globalPoints.find((p) => p.track_id === selectedId) ?? null;
  }, [globalPoints, selectedId]);

  const renderPoints = useMemo(() => {
    return globalPoints
      .map((point) => {
        const shifted = getShiftedCoords(point, coordMode);
        return shifted ? { point, shifted } : null;
      })
      .filter((entry): entry is { point: SongPoint; shifted: [number, number, number] } => !!entry);
  }, [globalPoints, coordMode]);

  const { positions, colors } = useMemo(() => {
    const pos = new Float32Array(renderPoints.length * 3);
    const col = new Float32Array(renderPoints.length * 3);

    renderPoints.forEach(({ point, shifted }, i) => {
      pos[i * 3] = shifted[0];
      pos[i * 3 + 1] = shifted[1];
      pos[i * 3 + 2] = shifted[2];

      const c = walkCurrentId === point.track_id
        ? COLOR_CURRENT
        : walkIds.has(point.track_id)
          ? COLOR_WALK
        : !walkActive && neighborIds.has(point.track_id)
          ? COLOR_NEIGHBOR
          : userSongIds.has(point.track_id)
            ? COLOR_USER
            : COLOR_GLOBAL;

      col[i * 3] = c.r;
      col[i * 3 + 1] = c.g;
      col[i * 3 + 2] = c.b;
    });

    return { positions: pos, colors: col };
  }, [renderPoints, userSongIds, neighborIds, walkIds, walkActive, walkCurrentId]);

  // Screen-space hover: project every point to NDC each frame and find the
  // nearest to the cursor in 2D. Immune to 3D threshold issues.
  useFrame(() => {
    const mouse = mouseNDC.current;
    if (!mouse) {
      hoveredRef.current = null;
      onHover(null);
      return;
    }

    const pxThresh = 20 / (size.height * 0.5);
    const threshSq = pxThresh * pxThresh;

    let bestIdx = -1;
    let bestDist = Infinity;

    for (let i = 0; i < renderPoints.length; i++) {
      tempVec.set(positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]);
      tempVec.project(camera);
      if (tempVec.z > 1) continue;

      const dx = tempVec.x - mouse.x;
      const dy = tempVec.y - mouse.y;
      const dSq = dx * dx + dy * dy;
      if (dSq < threshSq && dSq < bestDist) {
        bestDist = dSq;
        bestIdx = i;
      }
    }

    const found = bestIdx >= 0 ? renderPoints[bestIdx].point : null;
    hoveredRef.current = found;
    onHover(found);
  });

  const selectedShifted = selectedPoint ? getShiftedCoords(selectedPoint, coordMode) : null;

  return (
    <>
      <points ref={meshRef} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-color" args={[colors, 3]} />
        </bufferGeometry>
        <pointsMaterial
          vertexColors
          map={circleTexture}
          alphaTest={0.5}
          size={0.04}
          sizeAttenuation
          depthWrite={false}
          transparent
          opacity={0.9}
        />
      </points>
      {!walkActive && selectedPoint && selectedShifted && (
        <mesh position={[
          selectedShifted[0],
          selectedShifted[1],
          selectedShifted[2],
        ]}>
          <sphereGeometry args={[0.009, 16, 16]} />
          <meshBasicMaterial color="#FF2D2D" transparent opacity={1} />
        </mesh>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export default function PointCloudViewer(props: PointCloudViewerProps) {
  const { onPointClick, ...rest } = props;
  const [hoveredPoint, setHoveredPoint] = useState<SongPoint | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const mouseNDC = useRef<{ x: number; y: number } | null>(null);
  const hoveredRef = useRef<SongPoint | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cameraControlsRef = useRef<CameraControls>(null);
  const isInteracting = useRef(false);
  const resumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    setMousePos({ x: e.clientX, y: e.clientY });
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    mouseNDC.current = {
      x: ((e.clientX - rect.left) / rect.width) * 2 - 1,
      y: -((e.clientY - rect.top) / rect.height) * 2 + 1,
    };
  }, []);

  const handleMouseLeave = useCallback(() => {
    mouseNDC.current = null;
  }, []);

  // Click fires onPointClick with whichever point useFrame last found nearest
  const handleClick = useCallback(() => {
    if (hoveredRef.current) onPointClick(hoveredRef.current);
  }, [onPointClick]);

  function pauseRotation() {
    isInteracting.current = true;
    if (resumeTimer.current) clearTimeout(resumeTimer.current);
  }

  function scheduleResume(delay = 300) {
    if (resumeTimer.current) clearTimeout(resumeTimer.current);
    resumeTimer.current = setTimeout(() => {
      isInteracting.current = false;
    }, delay);
  }

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
      onMouseDown={pauseRotation}
      onMouseUp={() => scheduleResume(300)}
      onWheel={() => { pauseRotation(); scheduleResume(400); }}
    >
      <Canvas
        camera={{ position: [0, 0, 1.2], fov: 60, near: 0.01, far: 100 }}
        style={{ background: "#08090c", width: "100%", height: "100%" }}
      >
        <PointCloud
          {...rest}
          onHover={setHoveredPoint}
          mouseNDC={mouseNDC}
          hoveredRef={hoveredRef}
        />
        <WalkPathOverlay
          globalPoints={rest.globalPoints}
          walkPathIds={rest.walkPathIds}
          walkProgress={rest.walkProgress}
          coordMode={rest.coordMode}
        />
        <AutoRotate controlsRef={cameraControlsRef} isInteracting={isInteracting} />
        <CameraControls
          ref={cameraControlsRef}
          dampingFactor={0.06}
          azimuthRotateSpeed={0.5}
          polarRotateSpeed={0.5}
          dollySpeed={0.3}
          minDistance={0.08}
          maxDistance={3.5}
        />
      </Canvas>

      {hoveredPoint && (
        <div
          className="pointer-events-none fixed z-50 px-2 py-1 bg-black border border-white/20 font-mono text-xs text-white whitespace-nowrap"
          style={{ left: mousePos.x + 14, top: mousePos.y - 32 }}
        >
          <span className="font-black">{hoveredPoint.name}</span>
          <span className="text-white/50 ml-1">— {hoveredPoint.artist}</span>
        </div>
      )}
    </div>
  );
}
