"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Navbar from "../components/Navbar";
import PointCloudViewer from "../components/PointCloudViewer";
import ControlsOverlay, { ExploreMode } from "../components/ControlsOverlay";
import DensitySlider, { Topology } from "../components/DensitySlider";
import SongSidebar from "../components/SongSidebar";
import { usePointCloud } from "./hooks/usePointCloud";
import { useSongSelection } from "./hooks/useSongSelection";
import { useWalkState } from "./hooks/useWalkState";
import type { SongPoint } from "../lib/api";

export default function ExplorePage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [exploreMode, setExploreMode] = useState<ExploreMode>("manual");
  const [revealed, setRevealed] = useState(false);
  const [pointDensity, setPointDensity] = useState(50);
  const [topology, setTopology] = useState<Topology>("uniform");
  const coordMode = topology === "uniform" ? "uniform" : "raw";

  const userId = (session as { spotifyId?: string } | null)?.spotifyId ?? undefined;

  // Auth guard
  useEffect(() => {
    if (status === "unauthenticated") router.replace("/");
  }, [status, router]);

  useEffect(() => {
    const t = setTimeout(() => setRevealed(true), 50);
    return () => clearTimeout(t);
  }, []);

  // ── Hooks ────────────────────────────────────────────────────────────────

  const { globalPoints, userSongIds, isLoading } = usePointCloud(pointDensity, userId, status === "authenticated");

  const selection = useSongSelection(session);

  const walk = useWalkState(selection.selectedSong, selection.clearNeighbors);

  // Full merged point list — includes walk points so WalkPathOverlay can find them
  const allPoints = useMemo(
    () => [...globalPoints, ...selection.neighborPoints, ...walk.walkPoints],
    [globalPoints, selection.neighborPoints, walk.walkPoints],
  );

  // Fast lookup used by walk actions at call time
  const pointLookup = useMemo(
    () => new Map(allPoints.map((p) => [p.track_id, p])),
    [allPoints],
  );

  // ── Mode change: reset walk ───────────────────────────────────────────────

  const prevModeRef = { current: "manual" as ExploreMode };
  const handleModeChange = useCallback((mode: ExploreMode) => {
    if (mode !== prevModeRef.current) {
      prevModeRef.current = mode;
      walk.resetWalk();
    }
    setExploreMode(mode);
  }, [walk]);

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleSongSelect = useCallback((point: SongPoint) => {
    return selection.selectSong(point, pointLookup);
  }, [selection.selectSong, pointLookup]);

  const handleClose = useCallback(() => {
    selection.closeSidebar();
    walk.resetWalk();
  }, [selection.closeSidebar, walk.resetWalk]);

  const handleStartWalk = useCallback((opts?: { temperature?: number }) => {
    walk.startWalk(opts, pointLookup);
  }, [walk.startWalk, pointLookup]);

  const handleNextStep = useCallback(() => {
    walk.nextStep(
      pointLookup,
      (point) => selection.selectSong(point, pointLookup, { fetchNeighbors: false }),
      (id, title, artist) => {
        selection.setSidebarOpen(true);
        selection.setSelectedSong({ id, title, artist });
      },
    );
  }, [walk.nextStep, pointLookup, selection.selectSong, selection.setSidebarOpen, selection.setSelectedSong]);

  const handleRespawn = useCallback(() => {
    walk.respawnToSeed(
      pointLookup,
      (point) => selection.selectSong(point, pointLookup, { fetchNeighbors: false }),
      (id) => {
        selection.setSidebarOpen(true);
        selection.setSelectedSong({ id });
      },
    );
  }, [walk.respawnToSeed, pointLookup, selection.selectSong, selection.setSidebarOpen, selection.setSelectedSong]);

  const handleSkip = useCallback(() => {
    if (!selection.selectedSong) return;
    const currentIndex = globalPoints.findIndex((p) => p.track_id === selection.selectedSong!.id);
    const nextPoint = globalPoints[currentIndex + 1] ?? globalPoints[0];
    if (nextPoint) handleSongSelect(nextPoint);
  }, [selection.selectedSong, globalPoints, handleSongSelect]);

  // ── Early returns ─────────────────────────────────────────────────────────

  if (status === "loading") return null;
  if (status === "unauthenticated") return null;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <main className="relative w-screen h-screen bg-near-black overflow-hidden flex flex-col">

      {/* ── Black entrance overlay — fades away on mount ── */}
      <div
        className="fixed inset-0 z-50 pointer-events-none"
        style={{
          backgroundColor: "#080808",
          opacity: revealed ? 0 : 1,
          transition: revealed ? "opacity 400ms cubic-bezier(0.4, 0, 0.2, 1)" : "none",
        }}
      />

      {/* ── Navbar ── */}
      <Navbar />

      {/* ── Canvas + overlays ── */}
      <div className="relative flex-1 overflow-hidden">

        {/* Three.js canvas */}
        <div className="absolute inset-0 z-0">
          <PointCloudViewer
            globalPoints={allPoints}
            userSongIds={userSongIds}
            neighborIds={selection.neighborIds}
            walkIds={walk.walkIds}
            walkActive={walk.isWalking}
            walkPathIds={walk.walkPathIds}
            walkProgress={walk.walkStepIndex}
            coordMode={coordMode}
            onPointClick={handleSongSelect}
            selectedId={selection.selectedSong?.id ?? null}
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

        {/* ── Loading spinner ── */}
        {isLoading && (
          <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none">
            <div className="flex flex-col items-center gap-3">
              <div
                className="w-8 h-8 rounded-full border-2 border-transparent animate-spin"
                style={{ borderTopColor: "#1DB954", borderRightColor: "rgba(29,185,84,0.3)" }}
              />
              <span className="font-black text-[9px] uppercase tracking-widest text-white/40">
                Loading
              </span>
            </div>
          </div>
        )}

        {/* ── Density slider + legend — left edge ── */}
        <div className="absolute left-4 z-10 flex flex-col gap-4" style={{ top: "50%", transform: "translateY(-55%)" }}>
          <DensitySlider
            value={pointDensity}
            onChange={setPointDensity}
            topology={topology}
            onTopologyChange={setTopology}
          />

          {/* Legend */}
          <div
            className="flex flex-col gap-2 pl-4 pr-6 py-6 border-2 border-white/60"
            style={{
              width: "140px",
              backgroundColor: "#080808",
              boxShadow: "inset 0 0 0 2px rgba(255,255,255,0.2), 4px 4px 0px 0px rgba(255,255,255,0.35)",
            }}
          >
            {[
              { color: "#1DB954", label: "Your Tracks" },
              { color: "#FF2D2D", label: "Selected" },
              { color: "#FF6B35", label: "Nearest" },
              { color: "#A855F7", label: "Journey" },
              { color: "#4a4a5a", label: "All Songs" },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-2">
                <span
                  className="shrink-0 rounded-full"
                  style={{ width: 8, height: 8, backgroundColor: color }}
                />
                <span className="font-black text-[9px] uppercase tracking-widest text-white/70">
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Mode controls — bottom center ── */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10">
          <ControlsOverlay onModeChange={handleModeChange} />
        </div>

        {/* ── Song sidebar — floats right-4 ── */}
        <div
          className="absolute right-4 top-1/2 z-10 transition-all duration-300 ease-in-out"
          style={{
            transform: `translateY(-50%) translateX(${selection.sidebarOpen ? "0px" : "calc(100% + 2rem)"})`,
            opacity: selection.sidebarOpen ? 1 : 0,
            pointerEvents: selection.sidebarOpen ? "auto" : "none",
          }}
        >
          <SongSidebar
            song={selection.selectedSong}
            isOpen={selection.sidebarOpen}
            mode={exploreMode}
            onClose={handleClose}
            onSkip={handleSkip}
            onWalk={handleStartWalk}
            isWalking={walk.isWalking}
            walkAdventurous={walk.walkAdventurous}
            onWalkAdventurousChange={walk.setWalkAdventurous}
            onRespawn={handleRespawn}
            onNextStep={handleNextStep}
            walkProgress={walk.isWalking ? { current: walk.walkStepIndex, total: walk.walkSteps.length } : undefined}
          />
        </div>

      </div>
    </main>
  );
}