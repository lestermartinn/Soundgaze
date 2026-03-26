"use client";

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
  description?: string;
  isLoading?: boolean;
  isDescriptionLoading?: boolean;
}

interface SongSidebarProps {
  song: SongData | null;
  isOpen: boolean;
  mode?: "manual" | "random-walk";
  onClose: () => void;
  onSkip: () => void;
  onWalk?: (opts?: { temperature?: number }) => void;
  isWalking?: boolean;
  onRespawn?: () => void;
  walkAdventurous?: number;
  onWalkAdventurousChange?: (value: number) => void;
  onNextStep?: () => void;
  walkProgress?: { current: number; total: number };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SongSidebar({
  song,
  mode = "manual",
  onClose,
  onSkip,
  onWalk,
  isWalking = false,
  onRespawn,
  walkAdventurous = 50,
  onWalkAdventurousChange,
  onNextStep,
  walkProgress,
}: SongSidebarProps) {
  return (
    <>
      <style>{`
        .desc-scroll::-webkit-scrollbar { width: 3px; }
        .desc-scroll::-webkit-scrollbar-track { background: transparent; }
        .desc-scroll::-webkit-scrollbar-thumb { background: rgba(29,185,84,0.4); border-radius: 2px; }
        @keyframes walk-dot-pulse {
          0%, 100% { transform: scale(1); opacity: 0.55; }
          50% { transform: scale(1.45); opacity: 1; }
        }
      `}</style>

      <div
        className="flex flex-col border-2 border-white/60 overflow-hidden"
        style={{
          width: "360px",
          backgroundColor: "#080808",
          boxShadow: "inset 0 0 0 2px rgba(255,255,255,0.2), 4px 4px 0px 0px rgba(255,255,255,0.35)",
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

        {/* ── Spotify embed ── */}
        <div className="shrink-0 w-full" style={{ height: "152px" }}>
          {song && !song.isLoading ? (
            <iframe
              key={song.id}
              src={`https://open.spotify.com/embed/track/${song.id}?utm_source=generator&theme=0`}
              width="100%"
              height="152"
              allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
              loading="lazy"
              style={{ border: "none", display: "block" }}
            />
          ) : (
            <div
              className="w-full h-full flex items-center justify-center"
              style={{ backgroundColor: "#111" }}
            >
              <div
                className="w-5 h-5 rounded-full border-2 animate-spin"
                style={{ borderColor: "#1DB954", borderTopColor: "transparent" }}
              />
            </div>
          )}
        </div>

        {/* ── Song info + description + skip ── */}
        <div className="flex flex-col gap-3 p-4">

          {/* Title / artist / album */}
          {song && !song.isLoading ? (
            <div>
              <h2
                className="font-black uppercase leading-tight text-white tracking-tight line-clamp-2"
                style={{ fontSize: "1.05rem" }}
              >
                {song.title ?? song.id}
              </h2>
              {song.artist && (
                <p className="font-mono text-sm font-bold mt-1" style={{ color: "#1DB954" }}>
                  {song.artist}
                </p>
              )}
              {song.album && (
                <p className="font-mono text-xs text-white/30 mt-0.5 truncate">{song.album}</p>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="h-5 w-3/4 rounded animate-pulse" style={{ backgroundColor: "#1a1a1a" }} />
              <div className="h-3.5 w-1/2 rounded animate-pulse" style={{ backgroundColor: "#1a1a1a" }} />
            </div>
          )}

          {/* Gemini description — scrollable if long */}
          {song?.isDescriptionLoading ? (
            <div
              className="p-3 flex flex-col gap-2"
              style={{ backgroundColor: "#111", borderLeft: "2px solid #1DB954" }}
            >
              <div className="h-2.5 w-full rounded animate-pulse" style={{ backgroundColor: "#1a1a1a" }} />
              <div className="h-2.5 w-5/6 rounded animate-pulse" style={{ backgroundColor: "#1a1a1a" }} />
              <div className="h-2.5 w-4/6 rounded animate-pulse" style={{ backgroundColor: "#1a1a1a" }} />
            </div>
          ) : song?.description ? (
            <div
              className="p-3"
              style={{ backgroundColor: "#111", borderLeft: "2px solid #1DB954" }}
            >
              <p
                className="desc-scroll font-mono text-xs text-white/55 leading-relaxed overflow-y-auto pr-1"
                style={{ maxHeight: "100px" }}
              >
                {song.description}
              </p>
            </div>
          ) : null}

          {mode === "manual" && (
            <button
              onClick={onSkip}
              disabled={!song || song.isLoading}
              className="w-full flex items-center justify-center gap-2 font-black text-xs
                         uppercase tracking-widest py-2.5 border-2 transition-all
                         hover:-translate-y-px active:translate-y-0
                         disabled:opacity-25 disabled:cursor-not-allowed disabled:translate-y-0"
              style={{ borderColor: "rgba(255,255,255,0.25)", color: "rgba(255,255,255,0.6)" }}
            >
              <svg width="12" height="11" viewBox="0 0 12 11" fill="currentColor">
                <path d="M1 0.5L8 5.5L1 10.5V0.5Z" />
                <rect x="9.5" y="0.5" width="2.5" height="10" rx="0.5" />
              </svg>
              Skip
            </button>
          )}

          {mode === "random-walk" && onWalk && (
            <>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-white/45">
                    Adventurous
                  </span>
                  <span className="font-mono text-[10px] text-[#A855F7]">
                    {walkAdventurous}%
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-1.5">
                  {[
                    { label: "Local", value: 15 },
                    { label: "Balanced", value: 50 },
                    { label: "Wild", value: 90 },
                  ].map((preset) => {
                    const active = Math.abs(walkAdventurous - preset.value) <= 2;
                    return (
                      <button
                        key={preset.label}
                        type="button"
                        onClick={() => onWalkAdventurousChange?.(preset.value)}
                        className="font-mono text-[9px] uppercase tracking-widest py-1 border transition-all"
                        style={{
                          borderColor: active ? "#A855F7" : "rgba(168,85,247,0.35)",
                          color: active ? "#A855F7" : "rgba(168,85,247,0.75)",
                          backgroundColor: active ? "rgba(168,85,247,0.15)" : "transparent",
                        }}
                      >
                        {preset.label}
                      </button>
                    );
                  })}
                </div>

                <input
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  value={walkAdventurous}
                  onChange={(e) => onWalkAdventurousChange?.(Number(e.target.value))}
                  className="w-full accent-[#A855F7]"
                />
              </div>

              <button
                onClick={() => onWalk({ temperature: walkAdventurous / 100 })}
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
                {isWalking ? "Restart Listening" : "Start Listening"}
              </button>

              {isWalking && onNextStep && (
                <button
                  onClick={onNextStep}
                  className="w-full font-black text-xs uppercase tracking-widest py-3 px-4
                             border-2 transition-all
                             hover:-translate-y-px active:translate-y-0"
                  style={{
                    backgroundColor: "transparent",
                    borderColor: "rgba(168,85,247,0.5)",
                    color: "rgba(168,85,247,0.9)",
                  }}
                >
                  Next Song ({walkProgress?.current ?? 0}/{walkProgress?.total ?? 20})
                </button>
              )}

            </>
          )}

        </div>
      </div>
    </>
  );
}
