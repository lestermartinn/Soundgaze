"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Navbar from "../components/Navbar";
import PointCloudViewer from "../components/PointCloudViewer";
import ControlsOverlay, { ExploreMode } from "../components/ControlsOverlay";
import DensitySlider from "../components/DensitySlider";
import { fetchPoints, fetchSimilar, type SongPoint } from "../lib/api";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ExplorePage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  // Point cloud
  const [globalPoints, setGlobalPoints]   = useState<SongPoint[]>([]);
  const [userSongIds, setUserSongIds]     = useState<Set<string>>(new Set());
  const [neighborIds, setNeighborIds]     = useState<Set<string>>(new Set());
  const [coordMode]                        = useState<"raw" | "uniform">("uniform");

  // Sidebar
  const [selectedSong, setSelectedSong]   = useState<SongPoint | null>(null);
  const [sidebarOpen, setSidebarOpen]     = useState(false);
  const [isSaving, setIsSaving]           = useState(false);
  const [saveStatus, setSaveStatus]       = useState<"idle" | "saved" | "error">("idle");

  // Controls
  const [exploreMode, setExploreMode]     = useState<ExploreMode>("manual");
  const [pointDensity, setPointDensity]   = useState(50);
  void exploreMode;

  // Auth guard
  useEffect(() => {
    if (status === "unauthenticated") router.replace("/");
  }, [status, router]);

  // Fetch points — debounced on pointDensity / session
  useEffect(() => {
    const userId = (session as { spotifyId?: string } | null)?.spotifyId ?? undefined;
    const n = Math.max(10, pointDensity * 10); // 10–1000 points
    const timer = setTimeout(async () => {
      try {
        const data = await fetchPoints(n, userId);
        setGlobalPoints(data.global_sample);
        setUserSongIds(new Set(data.user_songs.map((p) => p.track_id)));
      } catch (err) {
        console.error("fetchPoints failed", err);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [pointDensity, session]);

  if (status === "loading") return null;
  if (status === "unauthenticated") return null;

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  async function onSongSelect(point: SongPoint) {
    setSidebarOpen(true);
    setSelectedSong(point);
    setSaveStatus("idle");
    try {
      const { songs } = await fetchSimilar(point.track_id);
      setNeighborIds(new Set(songs.map((s) => s.track_id)));
    } catch (err) {
      console.error("fetchSimilar failed", err);
    }
  }

  function closeSidebar() {
    setSidebarOpen(false);
    setSelectedSong(null);
    setNeighborIds(new Set());
    setSaveStatus("idle");
  }

  async function saveToLikedSongs() {
    if (!selectedSong || !session?.accessToken) return;
    setIsSaving(true);
    setSaveStatus("idle");
    try {
      const res = await fetch("https://api.spotify.com/v1/me/tracks", {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ids: [selectedSong.track_id] }),
      });
      setSaveStatus(res.ok ? "saved" : "error");
    } catch {
      setSaveStatus("error");
    } finally {
      setIsSaving(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <main className="relative w-screen h-screen bg-near-black overflow-hidden flex flex-col">

      {/* ── Navbar ── */}
      <Navbar />

      {/* ── Canvas + overlays ── */}
      <div className="relative flex-1 overflow-hidden">

        {/* Three.js canvas */}
        <div className="absolute inset-0 z-0">
          <PointCloudViewer
            globalPoints={globalPoints}
            userSongIds={userSongIds}
            neighborIds={neighborIds}
            coordMode={coordMode}
            onPointClick={onSongSelect}
          />
        </div>

        {/* ── Corner green vignettes ── */}
        <div
          className="absolute inset-0 z-0 pointer-events-none"
          style={{
            background: `
              radial-gradient(ellipse 18% 22% at 0% 0%,    rgba(29,185,84,0.20) 0%, transparent 100%),
              radial-gradient(ellipse 18% 22% at 100% 0%,  rgba(29,185,84,0.20) 0%, transparent 100%),
              radial-gradient(ellipse 18% 22% at 0% 100%,  rgba(29,185,84,0.20) 0%, transparent 100%),
              radial-gradient(ellipse 18% 22% at 100% 100%,rgba(29,185,84,0.20) 0%, transparent 100%)
            `,
            boxShadow: "inset 0 0 60px rgba(29,185,84,0.15)",
          }}
        />

        {/* ── Density slider — left edge, vertically centered ── */}
        <div className="absolute left-4 top-1/2 -translate-y-1/2 z-10">
          <DensitySlider value={pointDensity} onChange={setPointDensity} />
        </div>

        {/* ── Mode controls — bottom center ── */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10">
          <ControlsOverlay onModeChange={setExploreMode} />
        </div>

        {/* ── Sidebar — slides in from right on song select ── */}
        <aside
          className={`absolute top-0 right-0 h-full w-80 z-10
                      bg-off-white border-l-4 border-black
                      shadow-[-8px_0px_0px_0px_rgba(0,0,0,1)]
                      transition-transform duration-300 ease-in-out flex flex-col
                      ${sidebarOpen ? "translate-x-0" : "translate-x-full"}`}
        >
          {/* Sidebar header */}
          <div className="flex items-center justify-between px-4 py-3 bg-black border-b-4 border-black">
            <span className="font-black text-xs uppercase tracking-widest text-spotify-green">
              Now Exploring
            </span>
            <button
              onClick={closeSidebar}
              className="font-black text-white text-lg leading-none hover:text-spotify-green transition-colors"
              aria-label="Close sidebar"
            >
              ✕
            </button>
          </div>

          {/* Sidebar content */}
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
            {selectedSong ? (
              <>
                {/* Song info */}
                <div className="border-b-4 border-black pb-3">
                  <h2 className="font-black text-2xl uppercase leading-tight">
                    {selectedSong.name}
                  </h2>
                  <p className="font-mono font-bold text-sm text-black/60 mt-1">
                    {selectedSong.artist}
                  </p>
                  <p className="font-mono text-xs text-black/40 mt-1 uppercase tracking-widest">
                    {selectedSong.genre}
                  </p>
                </div>

                {/* Similar songs count */}
                {neighborIds.size > 0 && (
                  <div className="bg-black text-white p-3 border-4 border-black">
                    <p className="font-mono text-xs leading-relaxed">
                      <span className="text-[#FF6B35] font-black">{neighborIds.size}</span> similar songs highlighted in the cloud.
                    </p>
                  </div>
                )}

                {/* Save to Liked Songs */}
                <button
                  className="w-full neo-btn-primary text-sm mt-auto disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={saveToLikedSongs}
                  disabled={isSaving || saveStatus === "saved" || !session?.accessToken}
                >
                  {isSaving
                    ? "Saving..."
                    : saveStatus === "saved"
                    ? "✓ Saved to Liked Songs"
                    : saveStatus === "error"
                    ? "✕ Save Failed — Retry"
                    : "♥ Save to Liked Songs"}
                </button>
              </>
            ) : (
              <p className="font-mono text-sm text-black/40 text-center mt-8">
                Click a point in the universe to explore a song.
              </p>
            )}
          </div>
        </aside>

      </div>
    </main>
  );
}
