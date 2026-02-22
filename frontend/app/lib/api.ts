// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SongPoint {
  track_id: string;
  name: string;
  artist: string;
  genre: string;
  xyz_raw: [number, number, number];
  xyz_uniform: [number, number, number];
}

export interface PointsResponse {
  global_sample: SongPoint[];
  user_songs: SongPoint[];
}

export interface SimilarResponse {
  songs: SongPoint[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Set to true to use mock data
const USE_PLACEHOLDERS = true;

// ---------------------------------------------------------------------------
// Placeholder generators
// ---------------------------------------------------------------------------

function randomXyz(): [number, number, number] {
  // Uniform distribution inside a unit cube — replace with real UMAP range later
  return [
    (Math.random() - 0.5) * 2,
    (Math.random() - 0.5) * 2,
    (Math.random() - 0.5) * 2,
  ];
}

const GENRES = ["pop", "rock", "hip-hop", "electronic", "jazz", "classical", "r&b"];
const ARTISTS = ["Artist A", "Artist B", "Artist C", "Artist D", "Artist E"];

function makePlaceholderPoint(i: number): SongPoint {
  const raw = randomXyz();
  return {
    track_id: `mock_${i}`,
    name: `Track ${i}`,
    artist: ARTISTS[i % ARTISTS.length],
    genre: GENRES[i % GENRES.length],
    xyz_raw: raw,
    xyz_uniform: raw.map((v) => v * 0.9 + (Math.random() - 0.5) * 0.1) as [number, number, number],
  };
}

function makePlaceholderPoints(n: number): PointsResponse {
  const global_sample = Array.from({ length: n }, (_, i) => makePlaceholderPoint(i));
  // Mark a handful as "user songs"
  const user_songs = global_sample.slice(0, 5).map((p) => ({ ...p }));
  return { global_sample, user_songs };
}

function makePlaceholderSimilar(trackId: string, n: number): SimilarResponse {
  const songs = Array.from({ length: n }, (_, i) =>
    makePlaceholderPoint(parseInt(trackId.replace("mock_", ""), 10) + i + 1)
  );
  return { songs };
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/**
 * Fetch a sample of 3D song points.
 * Backend: GET /songs/3d?n=N&user_id=...
 */
export async function fetchPoints(n: number, userId?: string): Promise<PointsResponse> {
  if (USE_PLACEHOLDERS) return makePlaceholderPoints(n);

  const params = new URLSearchParams({ n: String(n) });
  if (userId) params.set("user_id", userId);
  const res = await fetch(`${API_BASE}/songs/3d?${params}`);
  if (!res.ok) throw new Error(`fetchPoints failed: ${res.status}`);
  return res.json();
}

/**
 * Fetch similar songs for a given track (ANN search via 8D vector).
 * Backend: GET /songs/{track_id}/similar?n=N
 */
export async function fetchSimilar(trackId: string, n = 10): Promise<SimilarResponse> {
  if (USE_PLACEHOLDERS) return makePlaceholderSimilar(trackId, n);

  const res = await fetch(`${API_BASE}/songs/${encodeURIComponent(trackId)}/similar?n=${n}`);
  if (!res.ok) throw new Error(`fetchSimilar failed: ${res.status}`);
  return res.json();
}
