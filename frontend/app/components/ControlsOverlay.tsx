"use client";

import { useState, useEffect, useRef, useCallback } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ExploreMode = "manual" | "random-walk" | "auto-play";

interface ControlsOverlayProps {
  onModeChange?: (mode: ExploreMode) => void;
  onDensityChange?: (density: number) => void;
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

export default function ControlsOverlay({ onModeChange, onDensityChange }: ControlsOverlayProps) {
  const [mode, setMode] = useState<ExploreMode>("manual");
  const [density, setDensity] = useState(50);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Switch mode and propagate upward
  const applyMode = useCallback(
    (next: ExploreMode) => {
      setMode(next);
      onModeChange?.(next);
    },
    [onModeChange]
  );

  // Reset the 15-second idle timer; only auto-switch if user is in manual mode
  const resetIdleTimer = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => {
      setMode((prev) => {
        if (prev === "manual") {
          onModeChange?.("random-walk");
          return "random-walk";
        }
        return prev;
      });
    }, IDLE_TIMEOUT_MS);
  }, [onModeChange]);

  // Attach window-level interaction listeners for idle detection
  useEffect(() => {
    const events: (keyof WindowEventMap)[] = [
      "mousemove",
      "mousedown",
      "keydown",
      "touchstart",
    ];
    events.forEach((e) =>
      window.addEventListener(e, resetIdleTimer, { passive: true })
    );
    resetIdleTimer(); // kick off the timer on mount

    return () => {
      events.forEach((e) => window.removeEventListener(e, resetIdleTimer));
      if (idleTimer.current) clearTimeout(idleTimer.current);
    };
  }, [resetIdleTimer]);

  function handleDensityChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = Number(e.target.value);
    setDensity(val);
    onDensityChange?.(val);
  }

  return (
    <div
      className="flex items-center gap-4 px-5 py-3
                 bg-near-black border-4 border-black
                 shadow-[6px_6px_0px_0px_#1DB954]"
    >
      {/* ── Mode toggle ── */}
      <div className="flex border-2 border-black overflow-hidden">
        {MODES.map(({ id, label }, i) => (
          <button
            key={id}
            onClick={() => applyMode(id)}
            className={`font-black text-xs uppercase tracking-widest px-3 py-2 transition-colors
                        ${i !== 0 ? "border-l-2 border-black" : ""}
                        ${mode === id
                          ? "bg-spotify-green text-black"
                          : "bg-transparent text-white hover:bg-white/10"
                        }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Divider ── */}
      <div className="w-px h-5 bg-white/20" />

      {/* ── Density slider ── */}
      <div className="flex items-center gap-2">
        <span className="font-black text-xs uppercase tracking-widest text-white/60 hidden sm:block">
          Density
        </span>
        <input
          type="range"
          min={1}
          max={100}
          value={density}
          onChange={handleDensityChange}
          className="w-28 accent-[#1DB954] cursor-pointer"
        />
        <span className="font-mono text-xs text-white/40 w-7 text-right tabular-nums">
          {density}
        </span>
      </div>
    </div>
  );
}
