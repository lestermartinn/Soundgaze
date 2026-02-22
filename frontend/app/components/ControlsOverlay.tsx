"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import gsap from "gsap";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ExploreMode = "manual" | "random-walk";

interface ControlsOverlayProps {
  onModeChange?: (mode: ExploreMode) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MODES: { id: ExploreMode; label: string }[] = [
  { id: "manual", label: "Manual" },
  { id: "random-walk", label: "Auto-Play" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ControlsOverlay({ onModeChange }: ControlsOverlayProps) {
  const [mode, setMode] = useState<ExploreMode>("manual");
  const pillNavRef = useRef<HTMLDivElement>(null);
  const pillRef = useRef<HTMLDivElement>(null);
  const btnRefs = useRef<(HTMLButtonElement | null)[]>([]);

  function movePill(index: number) {
    const btn = btnRefs.current[index];
    const pill = pillRef.current;
    if (!btn || !pill) return;

    gsap.to(pill, {
      x: btn.offsetLeft,
      width: btn.offsetWidth,
      duration: 0.3,
      ease: "power2.out",
    });
  }

  const applyMode = useCallback(
    (next: ExploreMode) => {
      setMode(next);
      onModeChange?.(next);
      movePill(MODES.findIndex((m) => m.id === next));
    },
    [onModeChange],
  );

  // Seed pill on first render
  useEffect(() => {
    const id = requestAnimationFrame(() => movePill(0));
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      ref={pillNavRef}
      className="relative flex items-center p-1.5 bg-near-black border-2 border-white/60"
      style={{ boxShadow: "inset 0 0 0 2px rgba(255,255,255,0.2), 4px 4px 0px 0px rgba(255,255,255,0.35)" }}
    >
      {/* Sliding pill */}
      <div
        ref={pillRef}
        className="absolute left-0 top-1.5 bottom-1.5 pointer-events-none border-2 border-black"
        style={{ backgroundColor: "#1DB954" }}
      />

      {MODES.map(({ id, label }, i) => (
        <button
          key={id}
          ref={(el) => { btnRefs.current[i] = el; }}
          onClick={() => applyMode(id)}
          className="relative z-10 px-8 py-3 font-black text-sm uppercase tracking-widest select-none transition-colors duration-100 text-center whitespace-nowrap"
          style={{ color: mode === id ? "#000" : "rgba(255,255,255,0.6)" }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
