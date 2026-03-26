"use client";

import { useState, useEffect } from "react";
import { fetchPoints, type SongPoint, type PointsResponse } from "../../lib/api";

export function usePointCloud(pointDensity: number, userId: string | undefined, sessionReady: boolean) {
  const [fullData, setFullData] = useState<PointsResponse | null>(null);
  const [globalPoints, setGlobalPoints] = useState<SongPoint[]>([]);
  const [userSongIds, setUserSongIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);

  // ── Fetch effect ─────────────────────────────────────────────────────────
  // Runs only when the user or session changes. Fetches the full max dataset
  // once and stores it — density changes never trigger a network call.

  useEffect(() => {
    if (!sessionReady) return;

    setFullData(null);
    setIsLoading(true);

    const timer = setTimeout(async () => {
      try {
        const data = await fetchPoints(2000, userId);
        setFullData(data);
      } catch (err) {
        console.error("fetchPoints failed", err);
      } finally {
        setIsLoading(false);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [userId, sessionReady]);

  // ── Display effect ────────────────────────────────────────────────────────
  // Runs whenever density or the fetched dataset changes.
  // Pure subsample — no network, always instant.

  useEffect(() => {
    if (!fullData) return;

    const t = pointDensity / 100;
    const maxGlobal = fullData.global_sample.length;
    const nGlobal = Math.max(0, Math.round(t * maxGlobal));

    const userIds = new Set(fullData.user_songs.map((p) => p.track_id));
    const globalSub = fullData.global_sample.slice(0, nGlobal);
    const globalIds = new Set(globalSub.map((p) => p.track_id));
    const merged = [
      ...globalSub,
      ...fullData.user_songs.filter((p) => !globalIds.has(p.track_id)),
    ];

    setGlobalPoints(merged);
    setUserSongIds(userIds);
  }, [pointDensity, fullData]);

  return { globalPoints, userSongIds, isLoading };
}
