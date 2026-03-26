"use client";

import { useState, useRef, useCallback } from "react";
import type { Session } from "next-auth";
import { fetchSimilar, fetchDescription, type SongPoint } from "../../lib/api";
import type { SongData } from "../../components/SongSidebar";

export function useSongSelection(session: Session | null) {
  const [selectedSong, setSelectedSong] = useState<SongData | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [neighborPoints, setNeighborPoints] = useState<SongPoint[]>([]);
  const [neighborIds, setNeighborIds] = useState<Set<string>>(new Set());

  // Abort controller for in-flight requests on the current selection
  const abortRef = useRef<AbortController | null>(null);

  const selectSong = useCallback(async (
    point: SongPoint,
    allPoints: Map<string, SongPoint>,
    opts: { fetchNeighbors?: boolean } = {},
  ) => {
    const { fetchNeighbors = true } = opts;
    // Cancel any in-flight requests from the previous selection
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const { signal } = controller;

    setSidebarOpen(true);
    setSelectedSong({ id: point.track_id, isLoading: true });

    // Kick off Gemini in parallel
    const geminiPromise = fetchDescription(point.name, point.artist, point.genre);

    if (fetchNeighbors) {
      fetchSimilar(point.track_id)
        .then(({ songs }) => {
          if (signal.aborted) return;
          const existingIds = new Set(allPoints.keys());
          setNeighborIds(new Set(songs.map((s) => s.track_id)));
          setNeighborPoints(songs.filter((s) => !existingIds.has(s.track_id)));
        })
        .catch((err) => {
          if (!signal.aborted) console.error("fetchSimilar failed", err);
        });
    } else {
      setNeighborIds(new Set());
      setNeighborPoints([]);
    }

    // Await Spotify first — fast and unblocks album art + preview
    let spotifyData = null;
    if (session?.accessToken) {
      try {
        const r = await fetch(`https://api.spotify.com/v1/tracks/${point.track_id}`, {
          headers: { Authorization: `Bearer ${session.accessToken}` },
          signal,
        });
        if (r.ok) spotifyData = await r.json();
      } catch {
        // Aborted or network error — fall through to point data
      }
    }

    if (signal.aborted) return;

    setSelectedSong({
      id: point.track_id,
      title: spotifyData?.name ?? point.name,
      artist: spotifyData?.artists?.map((a: { name: string }) => a.name).join(", ") ?? point.artist,
      album: spotifyData?.album?.name,
      albumArt: spotifyData?.album?.images?.[0]?.url ?? undefined,
      previewUrl: spotifyData?.preview_url ?? null,
      isDescriptionLoading: true,
    });

    // Fill in description when Gemini resolves
    try {
      const { description } = await geminiPromise;
      if (signal.aborted) return;
      setSelectedSong((prev) =>
        prev ? { ...prev, description, isDescriptionLoading: false } : prev,
      );
    } catch {
      if (!signal.aborted) {
        setSelectedSong((prev) =>
          prev ? { ...prev, isDescriptionLoading: false } : prev,
        );
      }
    }
  }, [session]);

  const clearNeighbors = useCallback(() => {
    setNeighborIds(new Set());
    setNeighborPoints([]);
  }, []);

  const closeSidebar = useCallback(() => {
    abortRef.current?.abort();
    setSidebarOpen(false);
    setSelectedSong(null);
    setNeighborIds(new Set());
    setNeighborPoints([]);
  }, []);

  return {
    selectedSong,
    setSelectedSong,
    sidebarOpen,
    setSidebarOpen,
    neighborPoints,
    neighborIds,
    selectSong,
    clearNeighbors,
    closeSidebar,
  };
}