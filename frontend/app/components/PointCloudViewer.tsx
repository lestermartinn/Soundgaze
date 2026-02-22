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

  const orderedPoints = useMemo(() => {
    if (!walkPathIds || walkPathIds.length < 2) return [] as THREE.Vector3[];
    const byId = new Map(globalPoints.map((p) => [p.track_id, p]));
    return walkPathIds
      .map((id) => byId.get(id))
      .filter((p): p is SongPoint => !!p)
      .map((p) => {
        const xyz = coordMode === "raw" ? p.xyz_raw : p.xyz_uniform;
        return new THREE.Vector3(xyz[0] - 0.5, xyz[1] - 0.5, xyz[2] - 0.5);
      });
  }, [walkPathIds, globalPoints, coordMode]);

  const visibleCount = Math.min(orderedPoints.length, Math.max(1, walkProgress + 1));
  const visiblePoints = useMemo(() => orderedPoints.slice(0, visibleCount), [orderedPoints, visibleCount]);
  const currentPoint = visiblePoints.length > 0 ? visiblePoints[visiblePoints.length - 1] : null;
  const nextPoint = useMemo(() => {
    const idx = Math.max(0, (walkProgress ?? 0) + 1);
    return idx < orderedPoints.length ? orderedPoints[idx] : null;
  }, [orderedPoints, walkProgress]);
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

    if (headRef.current && currentPoint) {
      headRef.current.position.copy(currentPoint);
      const pulse = 1 + 0.22 * (0.5 + 0.5 * Math.sin(t * 6));
      headRef.current.scale.setScalar(pulse);
    }

    if (nextRef.current && nextPoint) {
      nextRef.current.position.copy(nextPoint);
      const pulse = 1 + 0.22 * (0.5 + 0.5 * Math.sin(t * 5.2));
      nextRef.current.scale.setScalar(pulse);
    }

    if (nextGlowRef.current && nextPoint) {
      nextGlowRef.current.position.copy(nextPoint);
      const glowPulse = 1 + 0.3 * (0.5 + 0.5 * Math.sin(t * 4.1));
      nextGlowRef.current.scale.setScalar(glowPulse);
    }

    if (arrowRef.current && currentPoint && nextPoint) {
      const dir = new THREE.Vector3().subVectors(nextPoint, currentPoint).normalize();
      const arrowPos = new THREE.Vector3().copy(nextPoint).addScaledVector(dir, -0.0075);
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

      {nextPoint && (
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

  const { positions, colors } = useMemo(() => {
    const pos = new Float32Array(globalPoints.length * 3);
    const col = new Float32Array(globalPoints.length * 3);

    globalPoints.forEach((p, i) => {
      const xyz = coordMode === "raw" ? p.xyz_raw : p.xyz_uniform;
      pos[i * 3] = xyz[0] - 0.5;
      pos[i * 3 + 1] = xyz[1] - 0.5;
      pos[i * 3 + 2] = xyz[2] - 0.5;

      const c = walkCurrentId === p.track_id
        ? COLOR_CURRENT
        : walkIds.has(p.track_id)
          ? COLOR_WALK
        : !walkActive && neighborIds.has(p.track_id)
          ? COLOR_NEIGHBOR
          : userSongIds.has(p.track_id)
            ? COLOR_USER
            : COLOR_GLOBAL;

      col[i * 3] = c.r;
      col[i * 3 + 1] = c.g;
      col[i * 3 + 2] = c.b;
    });

    return { positions: pos, colors: col };
  }, [globalPoints, userSongIds, neighborIds, walkIds, walkActive, walkCurrentId, coordMode]);

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

    for (let i = 0; i < globalPoints.length; i++) {
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

    const found = bestIdx >= 0 ? globalPoints[bestIdx] : null;
    hoveredRef.current = found;
    onHover(found);
  });

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
      {!walkActive && selectedPoint && (
        <mesh position={[
          (coordMode === "raw" ? selectedPoint.xyz_raw[0] : selectedPoint.xyz_uniform[0]) - 0.5,
          (coordMode === "raw" ? selectedPoint.xyz_raw[1] : selectedPoint.xyz_uniform[1]) - 0.5,
          (coordMode === "raw" ? selectedPoint.xyz_raw[2] : selectedPoint.xyz_uniform[2]) - 0.5,
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
          dollySpeed={0.8}
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
