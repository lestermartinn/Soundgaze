"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Navbar from "../components/Navbar";
import PointCloudViewer from "../components/PointCloudViewer";
import ControlsOverlay, { ExploreMode } from "../components/ControlsOverlay";
import DensitySlider, { Topology } from "../components/DensitySlider";
import SongSidebar, { SongData } from "../components/SongSidebar";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ExplorePage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [selectedSong, setSelectedSong] = useState<SongData | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "error">("idle");

  const [exploreMode, setExploreMode] = useState<ExploreMode>("manual");
  const [pointDensity, setPointDensity] = useState(50);
  const [topology, setTopology] = useState<Topology>("uniform");
  void exploreMode;
  void pointDensity;
  void topology;

  useEffect(() => {
    if (status === "unauthenticated") router.replace("/");
  }, [status, router]);

  if (status === "loading") return null;
  if (status === "unauthenticated") return null;

  async function onSongSelect(songId: string) {
    setSidebarOpen(true);
    setSaveStatus("idle");
    // Show sidebar immediately with loading state while we fetch
    setSelectedSong({ id: songId, isLoading: true });

    if (!session?.accessToken) return;

    try {
      const res = await fetch(`https://api.spotify.com/v1/tracks/${songId}`, {
        headers: { Authorization: `Bearer ${session.accessToken}` },
      });
      if (!res.ok) {
        setSelectedSong({ id: songId });
        return;
      }
      const data = await res.json();
      setSelectedSong({
        id: songId,
        title: data.name,
        artist: data.artists.map((a: { name: string }) => a.name).join(", "),
        album: data.album?.name,
        albumArt: data.album?.images?.[0]?.url ?? undefined,
        previewUrl: data.preview_url ?? null,
        culturalDescription:
          "Cultural and genre context will appear here once the backend is connected.",
      });
    } catch {
      setSelectedSong({ id: songId });
    }
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
