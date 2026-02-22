"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Navbar from "../components/Navbar";
import PointCloudViewer from "../components/PointCloudViewer";
import ControlsOverlay, { ExploreMode } from "../components/ControlsOverlay";
import DensitySlider, { Topology } from "../components/DensitySlider";
import SongSidebar, { SongData } from "../components/SongSidebar";
import { fetchPoints, fetchSimilar, type SongPoint } from "../lib/api";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ExplorePage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  // Point cloud
  const [globalPoints, setGlobalPoints] = useState<SongPoint[]>([]);
  const [userSongIds, setUserSongIds]   = useState<Set<string>>(new Set());
  const [neighborIds, setNeighborIds]   = useState<Set<string>>(new Set());
  const [coordMode]                      = useState<"raw" | "uniform">("uniform");

  // Sidebar
  const [selectedSong, setSelectedSong] = useState<SongData | null>(null);
  const [sidebarOpen, setSidebarOpen]   = useState(false);
  const [isSaving, setIsSaving]         = useState(false);
  const [saveStatus, setSaveStatus]     = useState<"idle" | "saved" | "error">("idle");

  // Controls
  const [exploreMode, setExploreMode]   = useState<ExploreMode>("manual");
  const [pointDensity, setPointDensity] = useState(50);
  const [topology, setTopology]         = useState<Topology>("uniform");
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
    setSaveStatus("idle");
    setSelectedSong({ id: point.track_id, isLoading: true });

    // Fetch neighbor highlights
    try {
      const { songs } = await fetchSimilar(point.track_id);
      setNeighborIds(new Set(songs.map((s) => s.track_id)));
    } catch (err) {
      console.error("fetchSimilar failed", err);
    }

    // Fetch rich Spotify metadata
    if (!session?.accessToken) return;
    try {
      const res = await fetch(`https://api.spotify.com/v1/tracks/${point.track_id}`, {
        headers: { Authorization: `Bearer ${session.accessToken}` },
      });
      if (!res.ok) {
        setSelectedSong({ id: point.track_id });
        return;
      }
      const data = await res.json();
      setSelectedSong({
        id: point.track_id,
        title: data.name,
        artist: data.artists.map((a: { name: string }) => a.name).join(", "),
        album: data.album?.name,
        albumArt: data.album?.images?.[0]?.url ?? undefined,
        previewUrl: data.preview_url ?? null,
        culturalDescription:
          "Cultural and genre context will appear here once the backend is connected.",
      });
    } catch {
      setSelectedSong({ id: point.track_id });
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
        body: JSON.stringify({ ids: [selectedSong.id] }),
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
          <DensitySlider
            value={pointDensity}
            onChange={setPointDensity}
            topology={topology}
            onTopologyChange={setTopology}
          />
        </div>

        {/* ── Mode controls — bottom center ── */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10">
          <ControlsOverlay onModeChange={setExploreMode} />
        </div>

        {/* ── Song sidebar — floats right-4, mirrors DensitySlider position ── */}
        <div
          className="absolute right-4 top-1/2 z-10 transition-all duration-300 ease-in-out"
          style={{
            transform: `translateY(-50%) translateX(${sidebarOpen ? "0px" : "calc(100% + 2rem)"})`,
            opacity: sidebarOpen ? 1 : 0,
            pointerEvents: sidebarOpen ? "auto" : "none",
          }}
        >
          <SongSidebar
            song={selectedSong}
            isOpen={sidebarOpen}
            onClose={closeSidebar}
            onSave={saveToLikedSongs}
            isSaving={isSaving}
            saveStatus={saveStatus}
          />
        </div>

      </div>
    </main>
  );
}
