"use client";

import { useRef, useMemo, useCallback } from "react";
import { Canvas, ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Points, PointMaterial } from "@react-three/drei";
import * as THREE from "three";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SongPoint {
  id: string;
  position: [number, number, number]; // UMAP-reduced (x, y, z)
}

interface PointCloudProps {
  onPointClick: (songId: string) => void;
}

// ---------------------------------------------------------------------------
// Placeholder dataset — 1,000 random points in a sphere.
// Replace with real UMAP coordinates fetched from FastAPI.
// ---------------------------------------------------------------------------

function generatePlaceholderPoints(count = 1000): SongPoint[] {
  return Array.from({ length: count }, (_, i) => {
    // Uniform distribution inside a unit sphere
    const u = Math.random();
    const v = Math.random();
    const theta = 2 * Math.PI * u;
    const phi = Math.acos(2 * v - 1);
    const r = Math.cbrt(Math.random()) * 50; // radius up to 50 units
    return {
      id: `song_${i}`,
      position: [
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta),
        r * Math.cos(phi),
      ],
    };
  });
}

// ---------------------------------------------------------------------------
// Inner scene — separated so it runs inside <Canvas>
// ---------------------------------------------------------------------------

function PointCloud({
  points,
  onPointClick,
}: {
  points: SongPoint[];
  onPointClick: (songId: string) => void;
}) {
  const meshRef = useRef<THREE.Points>(null);

  // Flatten positions into a Float32Array for BufferGeometry
  const positions = useMemo(() => {
    const arr = new Float32Array(points.length * 3);
    points.forEach(({ position }, i) => {
      arr[i * 3] = position[0];
      arr[i * 3 + 1] = position[1];
      arr[i * 3 + 2] = position[2];
    });
    return arr;
  }, [points]);

  // Raycaster-based click: find the nearest point and fire the callback
  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      if (e.index === undefined) return;
      const song = points[e.index];
      if (song) onPointClick(song.id);
    },
    [points, onPointClick]
  );

  return (
    <Points
      ref={meshRef}
      positions={positions}
      stride={3}
      frustumCulled={false}
      onClick={handleClick}
    >
      <PointMaterial
        transparent
        color="#7c6af7"
        size={0.6}
        sizeAttenuation
        depthWrite={false}
        opacity={0.85}
      />
    </Points>
  );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export default function PointCloudViewer({ onPointClick }: PointCloudProps) {
  // Memoize so the dataset is stable across re-renders
  const points = useMemo(() => generatePlaceholderPoints(1000), []);

  return (
    <Canvas
      camera={{ position: [0, 0, 120], fov: 60, near: 0.1, far: 2000 }}
      style={{ background: "#08090c", width: "100%", height: "100%" }}
    >
      {/* Ambient + point light for future mesh objects */}
      <ambientLight intensity={0.4} />
      <pointLight position={[100, 100, 100]} intensity={1.2} />

      <PointCloud points={points} onPointClick={onPointClick} />

      {/* Orbit controls: rotate, zoom, pan */}
      <OrbitControls
        enableDamping
        dampingFactor={0.06}
        rotateSpeed={0.5}
        zoomSpeed={0.8}
      />
    </Canvas>
  );
}
