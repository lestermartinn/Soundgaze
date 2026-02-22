"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Navbar from "./components/Navbar";
import PointCloudViewer from "./components/PointCloudViewer";
import ControlsOverlay, { ExploreMode } from "./components/ControlsOverlay";
import DensitySlider from "./components/DensitySlider";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SelectedSong {
  id: string;
  title?: string;
  artist?: string;
  albumArt?: string;
  culturalDescription?: string;
  previewUrl?: string;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ExplorePage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [selectedSong, setSelectedSong] = useState<SelectedSong | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "error">("idle");

  // Controls state — Parker wires these into PointCloudViewer once ready
  const [exploreMode, setExploreMode] = useState<ExploreMode>("manual");
  const [pointDensity, setPointDensity] = useState(50);
  void exploreMode;
  void pointDensity;

  const isDev = process.env.NODE_ENV === "development";

  useEffect(() => {
    if (status === "unauthenticated" && !isDev) router.replace("/landing");
  }, [status, router, isDev]);

  if (status === "loading") return null;
  if (status === "unauthenticated" && !isDev) return null;

  function onSongSelect(songId: string) {
    setSidebarOpen(true);
    setSelectedSong({
      id: songId,
      title: "Song Title",
      artist: "Artist Name",
      culturalDescription: "Cultural and genre context will appear here once the backend is connected.",
    });
  }

  function closeSidebar() {
    setSidebarOpen(false);
    setSelectedSong(null);
    setSaveStatus("idle");
  }

  async function saveToLikedSongs() {
    if (!selectedSong || !session?.accessToken) return;
    setIsSaving(true);
    setSaveStatus("idle");
    try {
      const res = await fetch(`https://api.spotify.com/v1/me/tracks`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ids: [selectedSong.id] }),
      });
      setSaveStatus(res.ok ? "saved" : "error");
    } catch {
      setSaveStatus("error");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <main className="relative w-screen h-screen bg-near-black overflow-hidden flex flex-col">

      {/* ── Navbar ── */}
      <Navbar />

      {/* ── Canvas + overlays layer ── */}
      <div className="relative flex-1 overflow-hidden">

        {/* Three.js canvas — Parker mounts into this div */}
        <div id="canvas-container" className="absolute inset-0 z-0">
          <PointCloudViewer onPointClick={onSongSelect} />
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
                {/* Album art placeholder */}
                <div className="w-full aspect-square bg-black border-4 border-black flex items-center justify-center">
                  {selectedSong.albumArt ? (
                    <img
                      src={selectedSong.albumArt}
                      alt={selectedSong.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <span className="text-white/20 font-black text-sm uppercase tracking-widest">
                      No Art
                    </span>
                  )}
                </div>

                {/* Song info */}
                <div className="border-b-4 border-black pb-3">
                  <h2 className="font-black text-2xl uppercase leading-tight">
                    {selectedSong.title ?? selectedSong.id}
                  </h2>
                  {selectedSong.artist && (
                    <p className="font-mono font-bold text-sm text-black/60 mt-1">
                      {selectedSong.artist}
                    </p>
                  )}
                </div>

                {/* Cultural / genre description (Gemini) */}
                {selectedSong.culturalDescription && (
                  <div className="bg-black text-white p-3 border-4 border-black">
                    <p className="font-mono text-xs leading-relaxed">
                      {selectedSong.culturalDescription}
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
