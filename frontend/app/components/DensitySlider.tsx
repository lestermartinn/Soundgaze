"use client";

import { useRef } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Topology = "uniform" | "accurate";

interface DensitySliderProps {
  value: number;
  onChange: (value: number) => void;
  topology?: Topology;
  onTopologyChange?: (t: Topology) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TRACK_H = 170;
const THUMB_R = 8;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DensitySlider({
  value,
  onChange,
  topology = "uniform",
  onTopologyChange,
}: DensitySliderProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  function valueFromY(clientY: number): number {
    const rect = trackRef.current!.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
    return Math.round(100 - ratio * 99);
  }

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    dragging.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    onChange(valueFromY(e.clientY));
  }
  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (dragging.current) onChange(valueFromY(e.clientY));
  }
  function onPointerUp() { dragging.current = false; }

  const thumbPct = 1 - (value - 1) / 99;
  const thumbTop = thumbPct * TRACK_H;
  const greenH = TRACK_H - thumbTop;

  const isUniform = topology === "uniform";

  return (
    <div
      className="flex flex-col items-center gap-4 px-6 py-6 border-2 border-white/60"
      style={{
        backgroundColor: "#080808",
        width: "140px",
        boxShadow: "inset 0 0 0 2px rgba(255,255,255,0.2), 4px 4px 0px 0px rgba(255,255,255,0.35)",
      }}
    >

      {/* DENSITY label */}
      <span className="font-black text-[12px] uppercase tracking-widest text-white/70 select-none">
        Density
      </span>

      {/* Custom vertical slider */}
      <div
        className="relative flex items-center justify-center cursor-pointer select-none"
        style={{ width: "32px", height: `${TRACK_H}px` }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        {/* Gray track */}
        <div
          ref={trackRef}
          className="absolute rounded-full"
          style={{
            width: "3px",
            top: 0, bottom: 0,
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "rgba(255,255,255,0.15)",
          }}
        />
        {/* Green fill */}
        <div
          className="absolute rounded-full"
          style={{
            width: "3px",
            bottom: 0,
            height: `${greenH}px`,
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "#1DB954",
          }}
        />
        {/* Thumb */}
        <div
          className="absolute rounded-full"
          style={{
            width: `${THUMB_R * 2}px`,
            height: `${THUMB_R * 2}px`,
            top: `${thumbTop - THUMB_R}px`,
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "#1DB954",
            boxShadow: "0 0 8px rgba(29,185,84,0.8)",
          }}
        />
      </div>

      {/* ── Divider ── */}
      <div className="w-full my-1" style={{ height: "2px", backgroundColor: "rgba(255,255,255,0.25)" }} />

      {/* UNIFORM label */}
      <span className="font-black text-[12px] uppercase tracking-widest text-white/70 select-none">
        Uniform
      </span>

      {/* Vertical pill toggle */}
      <button
        onClick={() => onTopologyChange?.(isUniform ? "accurate" : "uniform")}
        aria-label="Toggle topology mode"
        className="relative flex-shrink-0 rounded-full transition-colors duration-300"
        style={{
          width: "38px",
          height: "64px",
          backgroundColor: isUniform ? "rgba(29,185,84,0.15)" : "rgba(255,255,255,0.05)",
          border: `2px solid ${isUniform ? "#1DB954" : "rgba(255,255,255,0.2)"}`,
        }}
      >
        <div
          className="absolute rounded-full transition-all duration-300"
          style={{
            width: "20px",
            height: "20px",
            left: "50%",
            transform: "translateX(-50%)",
            top: isUniform ? "6px" : "auto",
            bottom: isUniform ? "auto" : "6px",
            backgroundColor: isUniform ? "#1DB954" : "rgba(255,255,255,0.3)",
            boxShadow: isUniform ? "0 0 8px rgba(29,185,84,0.7)" : "none",
          }}
        />
      </button>

      {/* ACCURATE TOPOLOGY label */}
      <span className="font-black text-[12px] uppercase tracking-widest text-white/70 text-center leading-tight select-none">
        Accurate<br />Topology
      </span>

    </div>
  );
}
