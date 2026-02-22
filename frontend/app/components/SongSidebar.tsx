"use client";

import { useState, useRef, useEffect } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SongData {
  id: string;
  title?: string;
  artist?: string;
  album?: string;
  albumArt?: string;
  previewUrl?: string | null;
  culturalDescription?: string;
  isLoading?: boolean;
}

interface SongSidebarProps {
  song: SongData | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: () => void;
  isSaving: boolean;
  saveStatus: "idle" | "saved" | "error";
  onWalk?: () => void;
  isWalking?: boolean;
  onNextStep?: () => void;
  walkProgress?: { current: number; total: number };
}

// ---------------------------------------------------------------------------
// Equalizer bars — varied heights + timings for organic feel
// ---------------------------------------------------------------------------

const BARS = [
  { h: 20, delay: "0.00s", dur: "0.85s" },
  { h: 36, delay: "0.18s", dur: "0.72s" },
  { h: 28, delay: "0.35s", dur: "1.05s" },
  { h: 46, delay: "0.08s", dur: "0.78s" },
  { h: 40, delay: "0.28s", dur: "0.92s" },
  { h: 32, delay: "0.12s", dur: "0.68s" },
  { h: 24, delay: "0.22s", dur: "0.98s" },
  { h: 42, delay: "0.05s", dur: "0.82s" },
  { h: 30, delay: "0.30s", dur: "1.10s" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SongSidebar({
  song,
  isOpen,
  onClose,
  onSave,
  isSaving,
  saveStatus,
  onWalk,
  isWalking = false,
  onNextStep,
  walkProgress,
}: SongSidebarProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const rafRef = useRef<number | null>(null);

  // Reset + set up audio whenever the song changes
  useEffect(() => {
    setIsPlaying(false);
    setProgress(0);
    setCurrentTime(0);
    setDuration(0);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
    }

    const url = song?.previewUrl;
    if (!url) return;

    const audio = new Audio(url);
    audio.volume = 0.75;
    audioRef.current = audio;

    audio.addEventListener("loadedmetadata", () => setDuration(audio.duration));
    audio.addEventListener("ended", () => {
      setIsPlaying(false);
      setProgress(0);
      setCurrentTime(0);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    });

    return () => {
      audio.pause();
      audio.src = "";
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [song?.id, song?.previewUrl]);

  // Pause when card closes
  useEffect(() => {
    if (!isOpen && audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    }
  }, [isOpen]);

  function togglePlay() {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    } else {
      audio.play().catch(() => {});
      setIsPlaying(true);
      const tick = () => {
        setCurrentTime(audio.currentTime);
        setProgress(audio.currentTime / (audio.duration || 1));
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    }
  }

  function seek(e: React.MouseEvent<HTMLDivElement>) {
    const audio = audioRef.current;
    if (!audio) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    audio.currentTime = ratio * (audio.duration || 0);
    setProgress(ratio);
    setCurrentTime(audio.currentTime);
  }

  function fmt(s: number) {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  }

  const hasPreview = !!song?.previewUrl;

  return (
    <>
      <style>{`
        @keyframes eq-bounce {
          0%, 100% { transform: scaleY(0.15); }
          50%       { transform: scaleY(1); }
        }
      `}</style>

      {/* Floating card — width matches DensitySlider proportions but wider */}
      <div
        className="flex flex-col border-2 border-white/60 overflow-hidden"
        style={{
          width: "260px",
          maxHeight: "85vh",
          backgroundColor: "#080808",
          boxShadow:
            "inset 0 0 0 2px rgba(255,255,255,0.2), 4px 4px 0px 0px rgba(255,255,255,0.35)",
        }}
      >
        {/* ── Header ── */}
        <div
          className="flex items-center justify-between px-4 py-2.5 shrink-0"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}
        >
          <div className="flex items-center gap-2">
            <span className="w-1 h-3.5 rounded-full" style={{ backgroundColor: "#1DB954" }} />
            <span className="font-black text-[10px] uppercase tracking-widest text-white/50">
              Now Exploring
            </span>
          </div>
          <button
            onClick={onClose}
            className="font-black text-white/30 hover:text-white transition-colors text-sm leading-none"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* ── Scrollable body ── */}
        <div className="flex-1 overflow-y-auto flex flex-col min-h-0">

          {/* Album art + playback overlay */}
          <div className="w-full relative shrink-0 overflow-hidden" style={{ height: "160px" }}>

            {song?.albumArt ? (
              <img
                src={song.albumArt}
                alt={song.title}
                className="w-full h-full object-cover"
              />
            ) : (
              <div
                className="w-full h-full flex items-center justify-center"
                style={{ backgroundColor: "#111" }}
              >
                {song?.isLoading ? (
                  <div
                    className="w-5 h-5 rounded-full border-2 animate-spin"
                    style={{ borderColor: "#1DB954", borderTopColor: "transparent" }}
                  />
                ) : (
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" opacity="0.12">
                    <circle cx="12" cy="12" r="10" stroke="white" strokeWidth="1.2" />
                    <circle cx="12" cy="12" r="3.5" stroke="white" strokeWidth="1.2" />
                    <circle cx="12" cy="12" r="1" fill="white" />
                  </svg>
                )}
              </div>
            )}

            {/* Playback overlay — gradient + controls on top of art */}
            {hasPreview && !song?.isLoading && (
              <div
                className="absolute inset-0 flex flex-col justify-end"
                style={{
                  background:
                    "linear-gradient(to top, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.45) 45%, transparent 72%)",
                }}
              >
                <div className="flex flex-col gap-2.5 px-3 pb-3">

                  {/* Equalizer bars */}
                  <div className="flex items-end gap-[3px]" style={{ height: "44px" }}>
                    {BARS.map((bar, i) => (
                      <div
                        key={i}
                        style={{
                          width: "4px",
                          height: `${bar.h}px`,
                          borderRadius: "2px",
                          backgroundColor: "#1DB954",
                          transformOrigin: "bottom center",
                          animation: isPlaying
                            ? `eq-bounce ${bar.dur} ${bar.delay} ease-in-out infinite`
                            : "none",
                          transform: isPlaying ? undefined : "scaleY(0.2)",
                          transition: "transform 0.4s ease",
                          opacity: isPlaying ? 0.9 : 0.3,
                        }}
                      />
                    ))}
                  </div>

                  {/* Play/pause + scrubber */}
                  <div className="flex items-center gap-2.5">
                    <button
                      onClick={togglePlay}
                      className="shrink-0 w-8 h-8 flex items-center justify-center border-2 transition-all hover:-translate-y-px active:translate-y-0"
                      style={{
                        backgroundColor: "#1DB954",
                        borderColor: "#1DB954",
                        boxShadow: "2px 2px 0px 0px rgba(0,0,0,0.6)",
                      }}
                      aria-label={isPlaying ? "Pause" : "Play preview"}
                    >
                      {isPlaying ? (
                        <svg width="10" height="12" viewBox="0 0 10 12" fill="black">
                          <rect x="0.5" y="0.5" width="3" height="11" rx="0.5" />
                          <rect x="6.5" y="0.5" width="3" height="11" rx="0.5" />
                        </svg>
                      ) : (
                        <svg width="11" height="12" viewBox="0 0 11 12" fill="black">
                          <path d="M1.5 1.1L10 6L1.5 10.9V1.1Z" />
                        </svg>
                      )}
                    </button>

                    <div className="flex-1 flex flex-col gap-1">
                      {/* Scrubber track */}
                      <div
                        className="w-full h-[3px] cursor-pointer relative group"
                        style={{ backgroundColor: "rgba(255,255,255,0.15)" }}
                        onClick={seek}
                      >
                        <div
                          className="absolute top-0 left-0 h-full"
                          style={{ width: `${progress * 100}%`, backgroundColor: "#1DB954" }}
                        />
                        <div
                          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-2 h-2 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                          style={{
                            left: `${progress * 100}%`,
                            backgroundColor: "#1DB954",
                            boxShadow: "0 0 5px rgba(29,185,84,0.8)",
                          }}
                        />
                      </div>
                      <div className="flex justify-between">
                        <span className="font-mono text-[9px] text-white/40">{fmt(currentTime)}</span>
                        <span className="font-mono text-[9px] text-white/25">
                          {duration ? fmt(duration) : "0:30"} preview
                        </span>
                      </div>
                    </div>
                  </div>

                </div>
              </div>
            )}
          </div>

          {/* ── Song info + actions ── */}
          <div className="flex flex-col gap-3 p-4">

            {/* Title / artist / album */}
            {song && !song.isLoading ? (
              <div>
                <h2 className="font-black text-lg uppercase leading-tight text-white tracking-tight">
                  {song.title ?? song.id}
                </h2>
                {song.artist && (
                  <p className="font-mono text-sm font-bold mt-0.5" style={{ color: "#1DB954" }}>
                    {song.artist}
                  </p>
                )}
                {song.album && (
                  <p className="font-mono text-xs text-white/30 mt-0.5 truncate">
                    {song.album}
                  </p>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <div className="h-5 w-3/4 rounded animate-pulse" style={{ backgroundColor: "#1a1a1a" }} />
                <div className="h-3.5 w-1/2 rounded animate-pulse" style={{ backgroundColor: "#1a1a1a" }} />
              </div>
            )}

            {/* No preview notice */}
            {!hasPreview && !song?.isLoading && (
              <p className="font-mono text-[9px] uppercase tracking-widest text-white/20 text-center py-0.5">
                No preview available
              </p>
            )}

            {/* Cultural / Gemini description */}
            {song?.culturalDescription && (
              <div
                className="p-3"
                style={{
                  backgroundColor: "#111",
                  borderLeft: "2px solid #1DB954",
                }}
              >
                <p className="font-mono text-xs text-white/55 leading-relaxed">
                  {song.culturalDescription}
                </p>
              </div>
            )}

            {/* Divider */}
            <div style={{ height: "1px", backgroundColor: "rgba(255,255,255,0.08)" }} />

            {/* Walk button */}
            {onWalk && (
              <button
                onClick={onWalk}
                disabled={!song || song.isLoading}
                className="w-full font-black text-xs uppercase tracking-widest py-3 px-4
                           border-2 transition-all
                           hover:-translate-y-px active:translate-y-0
                           disabled:opacity-40 disabled:cursor-not-allowed disabled:translate-y-0"
                style={{
                  backgroundColor: isWalking ? "rgba(168,85,247,0.15)" : "transparent",
                  borderColor: "#A855F7",
                  color: "#A855F7",
                  boxShadow: isWalking ? "none" : "3px 3px 0px 0px rgba(0,0,0,0.5)",
                }}
              >
                {isWalking ? "Re-roll Walk" : "Random Walk"}
              </button>
            )}

            {/* Next step button */}
            {isWalking && (
              <button
                onClick={onNextStep}
                disabled={!onNextStep || (walkProgress !== undefined && walkProgress.current >= walkProgress.total)}
                className="w-full font-black text-xs uppercase tracking-widest py-3 px-4
                           border-2 transition-all
                           hover:-translate-y-px active:translate-y-0
                           disabled:opacity-40 disabled:cursor-not-allowed disabled:translate-y-0"
                style={{
                  backgroundColor: "transparent",
                  borderColor: "#A855F7",
                  color: "#A855F7",
                  boxShadow: "3px 3px 0px 0px rgba(0,0,0,0.5)",
                }}
              >
                {walkProgress && walkProgress.current >= walkProgress.total
                  ? "Walk Complete"
                  : `→ Next Step${walkProgress ? ` (${walkProgress.current}/${walkProgress.total})` : ""}`}
              </button>
            )}

            {/* Divider */}
            <div style={{ height: "1px", backgroundColor: "rgba(255,255,255,0.08)" }} />
          </div>
        </div>
      </div>
    </>
  );
}
