"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import gsap from "gsap";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ExploreMode = "manual" | "random-walk" | "auto-play";

interface ControlsOverlayProps {
  onModeChange?: (mode: ExploreMode) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MODES: { id: ExploreMode; label: string }[] = [
  { id: "manual",      label: "Manual"      },
  { id: "random-walk", label: "Random Walk" },
  { id: "auto-play",   label: "Auto-Play"   },
];

const IDLE_TIMEOUT_MS = 15_000;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ControlsOverlay({ onModeChange }: ControlsOverlayProps) {
  const [mode,         setMode]         = useState<ExploreMode>("manual");
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const idleTimer  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pillNavRef = useRef<HTMLDivElement>(null);
  const pillRef    = useRef<HTMLDivElement>(null);
  const btnRefs    = useRef<(HTMLButtonElement | null)[]>([]);

  function movePill(index: number) {
    const btn  = btnRefs.current[index];
    const nav  = pillNavRef.current;
    const pill = pillRef.current;
    if (!btn || !nav || !pill) return;
    const navRect = nav.getBoundingClientRect();
    const btnRect = btn.getBoundingClientRect();
    gsap.to(pill, { x: btnRect.left - navRect.left, width: btnRect.width, duration: 0.3, ease: "power2.out" });
  }

  const applyMode = useCallback(
    (next: ExploreMode) => {
      setMode(next);
      onModeChange?.(next);
      movePill(MODES.findIndex((m) => m.id === next));
    },
    [onModeChange],
  );

  const resetIdleTimer = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => {
      setMode((prev) => {
        if (prev !== "manual") return prev;
        onModeChange?.("random-walk");
        movePill(MODES.findIndex((m) => m.id === "random-walk"));
        return "random-walk";
      });
    }, IDLE_TIMEOUT_MS);
  }, [onModeChange]);

  // Seed pill on first render
  useEffect(() => {
    const id = requestAnimationFrame(() => movePill(0));
    return () => cancelAnimationFrame(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const events: (keyof WindowEventMap)[] = ["mousemove", "mousedown", "keydown", "touchstart"];
    events.forEach((e) => window.addEventListener(e, resetIdleTimer, { passive: true }));
    resetIdleTimer();
    return () => {
      events.forEach((e) => window.removeEventListener(e, resetIdleTimer));
      if (idleTimer.current) clearTimeout(idleTimer.current);
    };
  }, [resetIdleTimer]);

  return (
    <div
      ref={pillNavRef}
      className="relative flex items-center p-1.5
                 bg-near-black border-4 border-black
                 shadow-[6px_6px_0px_0px_#1DB954]"
      onMouseLeave={() => {
        setHoveredIndex(null);
        movePill(MODES.findIndex((m) => m.id === mode));
      }}
    >
      {/* Sliding pill */}
      <div
        ref={pillRef}
        className="absolute top-1.5 bottom-1.5 pointer-events-none border-2 border-black"
        style={{ backgroundColor: "#1DB954" }}
      />

      {MODES.map(({ id, label }, i) => {
        const onPill = hoveredIndex !== null ? hoveredIndex === i : mode === id;
        return (
          <button
            key={id}
            ref={(el) => { btnRefs.current[i] = el; }}
            onClick={() => applyMode(id)}
            onMouseEnter={() => { setHoveredIndex(i); movePill(i); }}
            className="relative z-10 px-8 py-3 font-black text-sm uppercase tracking-widest select-none transition-colors duration-100"
            style={{ color: onPill ? "#000" : "rgba(255,255,255,0.6)" }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
