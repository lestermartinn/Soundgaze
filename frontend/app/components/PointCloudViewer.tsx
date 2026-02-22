"use client";

import { useRef, useMemo, useCallback, useState } from "react";
import { Canvas, ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import { CameraControls } from "@react-three/drei";
import * as THREE from "three";
import type { SongPoint } from "../lib/api";

// ---------------------------------------------------------------------------
// Colors
// ---------------------------------------------------------------------------

const COLOR_GLOBAL   = new THREE.Color("#4a4a5a");
const COLOR_USER     = new THREE.Color("#1DB954");
const COLOR_NEIGHBOR = new THREE.Color("#FF6B35");

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface PointCloudViewerProps {
  globalPoints: SongPoint[];
  userSongIds: Set<string>;
  neighborIds: Set<string>;
  coordMode: "raw" | "uniform";
  onPointClick: (point: SongPoint) => void;
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
// Dynamic raycaster — keeps hit threshold proportional to camera distance
// so hover/click stays accurate at any zoom level
// ---------------------------------------------------------------------------

function DynamicRaycaster() {
  const { raycaster, camera } = useThree();
  useFrame(() => {
    const dist = camera.position.length();
    if (!raycaster.params.Points) raycaster.params.Points = { threshold: 0 };
    raycaster.params.Points.threshold = dist * 0.015;
  });
  return null;
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
      // ~0.06 rad/s → full rotation in ~105 seconds. Barely perceptible.
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
  coordMode,
  onPointClick,
  onHover,
}: PointCloudViewerProps & { onHover: (point: SongPoint | null) => void }) {
  const meshRef = useRef<THREE.Points>(null);

  const circleTexture = useMemo(() => makeCircleTexture(), []);

  const { positions, colors } = useMemo(() => {
    const pos = new Float32Array(globalPoints.length * 3);
    const col = new Float32Array(globalPoints.length * 3);

    globalPoints.forEach((p, i) => {
      const xyz = coordMode === "raw" ? p.xyz_raw : p.xyz_uniform;
      pos[i * 3]     = xyz[0];
      pos[i * 3 + 1] = xyz[1];
      pos[i * 3 + 2] = xyz[2];

      const c = neighborIds.has(p.track_id)
        ? COLOR_NEIGHBOR
        : userSongIds.has(p.track_id)
        ? COLOR_USER
        : COLOR_GLOBAL;

      col[i * 3]     = c.r;
      col[i * 3 + 1] = c.g;
      col[i * 3 + 2] = c.b;
    });

    return { positions: pos, colors: col };
  }, [globalPoints, userSongIds, neighborIds, coordMode]);

  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      if (e.index === undefined) return;
      const point = globalPoints[e.index];
      if (point) onPointClick(point);
    },
    [globalPoints, onPointClick]
  );

  const handlePointerMove = useCallback(
    (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      if (e.index === undefined) { onHover(null); return; }
      onHover(globalPoints[e.index] ?? null);
    },
    [globalPoints, onHover]
  );

  return (
    <points
      ref={meshRef}
      onClick={handleClick}
      onPointerMove={handlePointerMove}
      onPointerOut={() => onHover(null)}
      frustumCulled={false}
    >
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color"    args={[colors, 3]}    />
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
  );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export default function PointCloudViewer(props: PointCloudViewerProps) {
  const [hoveredPoint, setHoveredPoint] = useState<SongPoint | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const cameraControlsRef = useRef<CameraControls>(null);
  const isInteracting = useRef(false);
  const resumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    setMousePos({ x: e.clientX, y: e.clientY });
  }, []);

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
      className="relative w-full h-full"
      onMouseMove={handleMouseMove}
      onMouseDown={pauseRotation}
      onMouseUp={() => scheduleResume(300)}
      onWheel={() => { pauseRotation(); scheduleResume(400); }}
    >
      <Canvas
        camera={{ position: [0, 0, 3], fov: 60, near: 0.01, far: 100 }}
        style={{ background: "#08090c", width: "100%", height: "100%" }}
      >
        <DynamicRaycaster />
        <PointCloud {...props} onHover={setHoveredPoint} />
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
