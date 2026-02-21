"use client";

import { useEffect, useState } from "react";
import PointCloudViewer from "./components/PointCloudViewer";

type HealthStatus = "checking" | "ok" | "error";

export default function HomePage() {
  const [backendStatus, setBackendStatus] = useState<HealthStatus>("checking");
  const [selectedSongId, setSelectedSongId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<string[]>([]);

  // Verify backend connection on mount
  useEffect(() => {
    async function checkBackend() {
      try {
        const res = await fetch("/api/py/health");
        setBackendStatus(res.ok ? "ok" : "error");
      } catch {
        setBackendStatus("error");
      }
    }
    checkBackend();
  }, []);

  // Called when the user clicks a point in the 3D cloud
  async function handlePointClick(songId: string) {
    setSelectedSongId(songId);
    setRecommendations([]);

    try {
      const res = await fetch("/api/py/songs/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ song_id: songId, top_k: 5 }),
      });
      if (res.ok) {
        const data = await res.json();
        setRecommendations(data.recommendations ?? []);
      }
    } catch (err) {
      console.error("Recommendation fetch failed:", err);
    }
  }

  return (
    <main className="grid grid-rows-[48px_1fr] h-screen relative overflow-hidden">
      {/* ── Header ── */}
      <header className="flex items-center gap-3 px-5 bg-surface border-b border-divider text-[15px] font-semibold tracking-wide">
        <h1>Hacklytics 2025</h1>
        <span
          className="status-dot w-2.5 h-2.5 rounded-full transition-colors duration-300"
          data-status={backendStatus}
          title={`Backend: ${backendStatus}`}
        />
      </header>

      {/* ── 3D Viewport ── */}
      <section className="relative w-full h-full">
        <PointCloudViewer onPointClick={handlePointClick} />
      </section>

      {/* ── Topological Twins sidebar ── */}
      {selectedSongId && (
        <aside className="absolute top-[68px] right-5 w-[260px] bg-surface border border-divider rounded-lg p-4 z-10">
          <h2 className="text-[13px] font-bold tracking-widest uppercase text-accent mb-2.5">
            Topological Twins
          </h2>
          <p className="text-xs text-muted mb-1">
            Selected: <code className="text-primary font-mono">{selectedSongId}</code>
          </p>

          {recommendations.length === 0 ? (
            <p className="text-xs text-muted">Loading…</p>
          ) : (
            <ul className="flex flex-col gap-1.5 mt-2">
              {recommendations.map((id) => (
                <li key={id}>
                  <code className="text-xs text-primary font-mono">{id}</code>
                </li>
              ))}
            </ul>
          )}
        </aside>
      )}
    </main>
  );
}
