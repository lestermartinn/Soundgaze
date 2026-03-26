"use client";

import { useState, useCallback } from "react";
import { fetchWalk, type SongPoint, type WalkStep } from "../../lib/api";
import type { SongData } from "../../components/SongSidebar";

export function useWalkState(
  selectedSong: SongData | null,
  clearNeighbors: () => void,
) {
  const [walkPoints, setWalkPoints] = useState<SongPoint[]>([]);
  const [walkIds, setWalkIds] = useState<Set<string>>(new Set());
  const [walkSteps, setWalkSteps] = useState<WalkStep[]>([]);
  const [isWalking, setIsWalking] = useState(false);
  const [walkStepIndex, setWalkStepIndex] = useState(0);
  const [walkSeedId, setWalkSeedId] = useState<string | null>(null);
  const [walkAdventurous, setWalkAdventurous] = useState(50);

  const walkPathIds: string[] = !walkSeedId || !isWalking
    ? []
    : [walkSeedId, ...walkSteps.map((s) => s.track_id)];

  /**
   * Start a new walk from the currently selected song.
   * pointLookup is passed at call time so it always reflects the latest merged points.
   */
  const startWalk = useCallback(async (
    opts: { temperature?: number } | undefined,
    pointLookup: Map<string, SongPoint>,
  ) => {
    if (!selectedSong) return;
    const temp = Math.max(0, Math.min(1, opts?.temperature ?? walkAdventurous / 100));
    const dynamicK = Math.round(18 + temp * 110);
    const dynamicRestartProb = Math.max(0, 0.35 * (1 - temp));

    clearNeighbors();
    setIsWalking(true);
    setWalkStepIndex(0);
    setWalkSeedId(selectedSong.id);

    try {
      const result = await fetchWalk(selectedSong.id, {
        steps: 20,
        temperature: temp,
        k: dynamicK,
        restartProb: dynamicRestartProb,
      });
      const steps = result.path.slice(1);
      const newWalkPoints: SongPoint[] = [];
      const allWalkIds = new Set<string>();

      for (const step of steps) {
        allWalkIds.add(step.track_id);
        if (!pointLookup.has(step.track_id) && step.xyz_raw && step.xyz_uniform) {
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
  }, [selectedSong, walkAdventurous, clearNeighbors]);

  /**
   * Advance to the next walk step.
   * pointLookup, selectSong, and openFallback are passed at call time.
   */
  const nextStep = useCallback(async (
    pointLookup: Map<string, SongPoint>,
    selectSong: (point: SongPoint) => Promise<void>,
    openFallback: (id: string, title?: string, artist?: string) => void,
  ) => {
    if (walkStepIndex >= walkSteps.length) return;
    const step = walkSteps[walkStepIndex];
    setWalkStepIndex((i) => i + 1);
    const point = pointLookup.get(step.track_id);
    if (point) {
      await selectSong(point);
    } else {
      openFallback(step.track_id, step.name, step.artist);
    }
  }, [walkStepIndex, walkSteps]);

  /**
   * Jump back to the walk seed song.
   * pointLookup, selectSong, and openFallback are passed at call time.
   */
  const respawnToSeed = useCallback(async (
    pointLookup: Map<string, SongPoint>,
    selectSong: (point: SongPoint) => Promise<void>,
    openFallback: (id: string) => void,
  ) => {
    if (!walkSeedId) return;
    setWalkStepIndex(0);
    const point = pointLookup.get(walkSeedId);
    if (point) {
      await selectSong(point);
    } else {
      openFallback(walkSeedId);
    }
  }, [walkSeedId]);

  const resetWalk = useCallback(() => {
    setWalkIds(new Set());
    setWalkPoints([]);
    setWalkSteps([]);
    setIsWalking(false);
    setWalkStepIndex(0);
    setWalkSeedId(null);
  }, []);

  return {
    walkPoints,
    walkIds,
    walkSteps,
    isWalking,
    walkStepIndex,
    walkSeedId,
    walkPathIds,
    walkAdventurous,
    setWalkAdventurous,
    startWalk,
    nextStep,
    respawnToSeed,
    resetWalk,
  };
}
