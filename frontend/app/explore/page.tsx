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
  const [globalPoints, setGlobalPoints]     = useState<SongPoint[]>([]);
  const [neighborPoints, setNeighborPoints] = useState<SongPoint[]>([]);
  const [userSongIds, setUserSongIds]       = useState<Set<string>>(new Set());
  const [neighborIds, setNeighborIds]       = useState<Set<string>>(new Set());

  // Sidebar
  const [selectedSong, setSelectedSong] = useState<SongData | null>(null);
  const [sidebarOpen, setSidebarOpen]   = useState(false);
  const [isSaving, setIsSaving]         = useState(false);
  const [saveStatus, setSaveStatus]     = useState<"idle" | "saved" | "error">("idle");

  // Controls
  const [exploreMode, setExploreMode]   = useState<ExploreMode>("manual");
  const [pointDensity, setPointDensity] = useState(50);
  const [topology, setTopology]         = useState<Topology>("uniform");
  const coordMode = topology === "uniform" ? "uniform" : "raw";
  const [isLoadingPoints, setIsLoadingPoints] = useState(false);
  void exploreMode;

  // Auth guard
  useEffect(() => {
    if (status === "unauthenticated") router.replace("/");
  }, [status, router]);

  // Fetch points — debounced on pointDensity / session
  // Quadratic scale: slider 1–100 → ~10–5000 points for better high-density reach
  useEffect(() => {
    const userId = (session as { spotifyId?: string } | null)?.spotifyId ?? undefined;
    const t = pointDensity / 100;
    const n = Math.min(5000, Math.max(10, Math.round(t * t * 5000)));
    setIsLoadingPoints(true);
    const timer = setTimeout(async () => {
      try {
        const data = await fetchPoints(n, userId);
        const userIds = new Set(data.user_songs.map((p) => p.track_id));
        // Merge user songs into the rendered set so they always appear in the cloud
        const globalIds = new Set(data.global_sample.map((p) => p.track_id));
        const merged = [
          ...data.global_sample,
          ...data.user_songs.filter((p) => !globalIds.has(p.track_id)),
        ];
        setGlobalPoints(merged);
        setUserSongIds(userIds);
      } catch (err) {
        console.error("fetchPoints failed", err);
      } finally {
        setIsLoadingPoints(false);
      }
    }, 400);
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

    // Fetch neighbor highlights — add any not already in the cloud as extra points
    try {
      const { songs } = await fetchSimilar(point.track_id);
      const existingIds = new Set(globalPoints.map((p) => p.track_id));
      setNeighborIds(new Set(songs.map((s) => s.track_id)));
      setNeighborPoints(songs.filter((s) => !existingIds.has(s.track_id)));
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
    setNeighborPoints([]);
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
            globalPoints={[...globalPoints, ...neighborPoints]}
            userSongIds={userSongIds}
            neighborIds={neighborIds}
            coordMode={coordMode}
            onPointClick={onSongSelect}
          />
        </div>

        {/* ── Loading spinner ── */}
        {isLoadingPoints && (
          <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none">
            <div
              className="rounded-full border-2 border-transparent animate-spin"
              style={{
                width: 40,
                height: 40,
                borderTopColor: "#1DB954",
                borderRightColor: "rgba(29,185,84,0.3)",
              }}
            />
          </div>
        )}

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
