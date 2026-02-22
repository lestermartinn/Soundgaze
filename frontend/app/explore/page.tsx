"use client";

import { useState, useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Navbar from "../components/Navbar";
import PointCloudViewer from "../components/PointCloudViewer";
import ControlsOverlay, { ExploreMode } from "../components/ControlsOverlay";
import DensitySlider, { Topology } from "../components/DensitySlider";
import SongSidebar, { SongData } from "../components/SongSidebar";
import { fetchPoints, fetchSimilar, fetchDescription, fetchWalk, type SongPoint, type WalkStep, type PointsResponse } from "../lib/api";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ExplorePage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  // Point cloud
  const [globalPoints, setGlobalPoints] = useState<SongPoint[]>([]);
  const [neighborPoints, setNeighborPoints] = useState<SongPoint[]>([]);
  const [userSongIds, setUserSongIds] = useState<Set<string>>(new Set());
  const [neighborIds, setNeighborIds] = useState<Set<string>>(new Set());

  // Sidebar
  const [selectedSong, setSelectedSong] = useState<SongData | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Walk
  const [walkPoints, setWalkPoints] = useState<SongPoint[]>([]);
  const [walkIds, setWalkIds] = useState<Set<string>>(new Set());
  const [walkSteps, setWalkSteps] = useState<WalkStep[]>([]);
  const [isWalking, setIsWalking] = useState(false);
  const [walkStepIndex, setWalkStepIndex] = useState(0);
  const [walkSeedId, setWalkSeedId] = useState<string | null>(null);
  const [walkSeedPoint, setWalkSeedPoint] = useState<SongPoint | null>(null);
  const [walkAdventurous, setWalkAdventurous] = useState(50);

  // Controls
  const [exploreMode, setExploreMode] = useState<ExploreMode>("manual");
  const [revealed, setRevealed] = useState(false);
  const [pointDensity, setPointDensity] = useState(50);
  const [topology, setTopology] = useState<Topology>("uniform");
  const coordMode = topology === "uniform" ? "uniform" : "raw";
  void exploreMode;

  // Cache: stores the largest dataset fetched so far.
  // Slider moving DOWN subsamples from this — no network call.
  // Slider moving UP beyond cache size triggers a backend fetch.
  const pointCacheRef = useRef<PointsResponse | null>(null);
  const cacheUserIdRef = useRef<string | undefined>(undefined);
  const prevModeRef = useRef<ExploreMode>("manual");

  // Auth guard
  useEffect(() => {
    if (status === "unauthenticated") router.replace("/");
  }, [status, router]);

  useEffect(() => {
    const t = setTimeout(() => setRevealed(true), 50);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (prevModeRef.current === exploreMode) return;
    prevModeRef.current = exploreMode;
    setWalkIds(new Set());
    setWalkPoints([]);
    setWalkSteps([]);
    setIsWalking(false);
    setWalkStepIndex(0);
    setWalkSeedId(null);
    setWalkSeedPoint(null);
  }, [exploreMode]);

  // Fetch points — debounced on pointDensity / session
  // Quadratic scale: slider 1–100 → ~10–5000 points for better high-density reach
  useEffect(() => {
    const userId = (session as { spotifyId?: string } | null)?.spotifyId ?? undefined;
    const t = pointDensity / 100;
    const n = Math.min(5000, Math.max(10, Math.round(t * t * 5000)));

    // Invalidate cache when user changes (e.g. different login)
    if (userId !== cacheUserIdRef.current) {
      pointCacheRef.current = null;
      cacheUserIdRef.current = userId;
    }

    const cache = pointCacheRef.current;
    const cacheSize = cache
      ? cache.global_sample.length + cache.user_songs.length
      : 0;

    // ── Cache hit: subsample locally, no network call ──────────────────────
    if (cache && n <= cacheSize) {
      const userIds = new Set(cache.user_songs.map((p) => p.track_id));
      const nGlobal = Math.max(0, n - cache.user_songs.length);
      const globalSub = cache.global_sample.slice(0, nGlobal);
      const globalIds = new Set(globalSub.map((p) => p.track_id));
      const merged = [
        ...globalSub,
        ...cache.user_songs.filter((p) => !globalIds.has(p.track_id)),
      ];
      setGlobalPoints(merged);
      setUserSongIds(userIds);
      return;
    }

    // ── Cache miss: fetch from backend, then update cache ─────────────────
    const timer = setTimeout(async () => {
      try {
        const data = await fetchPoints(n, userId);
        pointCacheRef.current = data; // store as new high-water mark
        const userIds = new Set(data.user_songs.map((p) => p.track_id));
        const globalIds = new Set(data.global_sample.map((p) => p.track_id));
        const merged = [
          ...data.global_sample,
          ...data.user_songs.filter((p) => !globalIds.has(p.track_id)),
        ];
        setGlobalPoints(merged);
        setUserSongIds(userIds);
      } catch (err) {
        console.error("fetchPoints failed", err);
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
    setSelectedSong({ id: point.track_id, isLoading: true });

    // Kick off neighbors + Gemini in parallel — don't block album art on either
    const geminiPromise = fetchDescription(point.name, point.artist, point.genre);

    fetchSimilar(point.track_id)
      .then(({ songs }) => {
        const existingIds = new Set(globalPoints.map((p) => p.track_id));
        setNeighborIds(new Set(songs.map((s) => s.track_id)));
        setNeighborPoints(songs.filter((s) => !existingIds.has(s.track_id)));
      })
      .catch((err) => console.error("fetchSimilar failed", err));

    // Await Spotify first — it's fast (~200ms) and unblocks album art + preview
    let spotifyData = null;
    if (session?.accessToken) {
      try {
        const r = await fetch(`https://api.spotify.com/v1/tracks/${point.track_id}`, {
          headers: { Authorization: `Bearer ${session.accessToken}` },
        });
        if (r.ok) spotifyData = await r.json();
      } catch { /* fall through to point data */ }
    }

    // Show album art, title, artist, preview immediately — description still loading
    setSelectedSong({
      id: point.track_id,
      title: spotifyData?.name ?? point.name,
      artist: spotifyData?.artists?.map((a: { name: string }) => a.name).join(", ") ?? point.artist,
      album: spotifyData?.album?.name,
      albumArt: spotifyData?.album?.images?.[0]?.url ?? undefined,
      previewUrl: spotifyData?.preview_url ?? null,
      isDescriptionLoading: true,
    });

    // Await Gemini and fill in description when ready
    try {
      const { description } = await geminiPromise;
      setSelectedSong((prev) => prev ? { ...prev, culturalDescription: description, isDescriptionLoading: false } : prev);
    } catch {
      setSelectedSong((prev) => prev ? { ...prev, isDescriptionLoading: false } : prev);
    }
  }

  function closeSidebar() {
    setSidebarOpen(false);
    setSelectedSong(null);
    setNeighborIds(new Set());
    setNeighborPoints([]);
    setWalkIds(new Set());
    setWalkPoints([]);
    setWalkSteps([]);
    setIsWalking(false);
    setWalkStepIndex(0);
    setWalkSeedId(null);
    setWalkSeedPoint(null);
  }

  async function startWalk(opts?: { temperature?: number }) {
    if (!selectedSong) return;
    const temp = Math.max(0, Math.min(1, opts?.temperature ?? walkAdventurous / 100));
    const dynamicK = Math.round(18 + temp * 110);
    const dynamicRestartProb = Math.max(0, 0.35 * (1 - temp));
    const dynamicNoRepeatWindow = Math.round(2 + temp * 8);

    const seedPoint = [...globalPoints, ...neighborPoints, ...walkPoints].find(
      (p) => p.track_id === selectedSong.id,
    ) ?? null;

    setIsWalking(true);
    setWalkStepIndex(0);
    setWalkSeedId(selectedSong.id);
    setWalkSeedPoint(seedPoint);
    try {
      const result = await fetchWalk(selectedSong.id, {
        steps: 20,
        temperature: temp,
        k: dynamicK,
        restartProb: dynamicRestartProb,
        noRepeatWindow: dynamicNoRepeatWindow,
      });
      const steps = result.path.slice(1);

      const existingIds = new Set([...globalPoints, ...neighborPoints].map((p) => p.track_id));
      const newWalkPoints: SongPoint[] = [];
      const allWalkIds = new Set<string>();

      for (const step of steps) {
        allWalkIds.add(step.track_id);
        if (!existingIds.has(step.track_id) && step.xyz_raw && step.xyz_uniform) {
          newWalkPoints.push({
            track_id: step.track_id,
            name: step.name ?? "",
            artist: step.artist ?? "",
            genre: step.genre ?? "",
            xyz_raw: step.xyz_raw as [number, number, number],
            xyz_uniform: step.xyz_uniform as [number, number, number],
          });
        }
      }

      setWalkIds(allWalkIds);
      setWalkPoints(newWalkPoints);
      setWalkSteps(steps);
    } catch (err) {
      console.error("fetchWalk failed", err);
      setIsWalking(false);
    }
  }

  async function respawnToSeed() {
    if (!walkSeedId) return;
    setWalkStepIndex(0);

    const point = [...globalPoints, ...neighborPoints, ...walkPoints].find(
      (p) => p.track_id === walkSeedId,
    ) ?? walkSeedPoint;

    if (point) {
      await onSongSelect(point);
      return;
    }

    setSidebarOpen(true);
    setSelectedSong({ id: walkSeedId });
  }

  const walkPathIds = !walkSeedId || !isWalking
    ? []
    : [walkSeedId, ...walkSteps.map((s) => s.track_id)];

  async function nextStep() {
    if (walkStepIndex >= walkSteps.length) return;
    const step = walkSteps[walkStepIndex];
    setWalkStepIndex((i) => i + 1);
    const point = [...globalPoints, ...neighborPoints, ...walkPoints].find(
      (p) => p.track_id === step.track_id,
    );
    if (point) {
      await onSongSelect(point);
    } else {
      setSidebarOpen(true);
      setSelectedSong({ id: step.track_id, title: step.name, artist: step.artist });
    }
  }

  function skipToNext() {
    if (!selectedSong) return;
    const currentIndex = globalPoints.findIndex((p) => p.track_id === selectedSong.id);
    const nextPoint = globalPoints[currentIndex + 1] ?? globalPoints[0];
    if (nextPoint) onSongSelect(nextPoint);
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

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
            globalPoints={[...globalPoints, ...neighborPoints, ...walkPoints]}
            userSongIds={userSongIds}
            neighborIds={neighborIds}
            walkIds={walkIds}
            walkActive={isWalking}
            walkPathIds={walkPathIds}
            walkProgress={walkStepIndex}
            coordMode={coordMode}
            onPointClick={onSongSelect}
            selectedId={selectedSong?.id ?? null}
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
            mode={exploreMode}
            onClose={closeSidebar}
            onSkip={skipToNext}
            onWalk={startWalk}
            isWalking={isWalking}
            walkAdventurous={walkAdventurous}
            onWalkAdventurousChange={setWalkAdventurous}
            onRespawn={respawnToSeed}
            onNextStep={nextStep}
            walkProgress={isWalking ? { current: walkStepIndex, total: walkSteps.length } : undefined}
          />
        </div>

      </div>
    </main>
  );
}
