# Hacklytics 2025 — Hackathon Boilerplate

> Explore your musical DNA as coordinates in an interactive 3-D universe. Find your **Topological Twins** — songs from different corners of the world that share nearly identical audio fingerprints.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript |
| 3-D Rendering | Three.js via `@react-three/fiber` + `@react-three/drei` |
| Backend | FastAPI (Python 3.11+) |
| ML — Similarity | Cosine similarity (brute-force → swap for FAISS) |
| ML — Mapping | UMAP 3-D reduction (`umap-learn`) |
| Spotify Data | `spotipy` |

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

Next.js proxies all `/api/py/*` requests to `http://localhost:8000` — no CORS setup needed.

---

## Project Structure

```
Hacklytics/
├── frontend/
│   ├── app/
│   │   ├── layout.tsx              Root layout
│   │   ├── page.tsx                Home: backend health check + sidebar
│   │   ├── page.module.css
│   │   ├── globals.css
│   │   └── components/
│   │       └── PointCloudViewer.tsx  Three.js 3-D point cloud
│   ├── lib/                        (shared utilities go here)
│   ├── next.config.ts              Proxy /api/py/ → localhost:8000
│   ├── package.json
│   └── tsconfig.json
│
└── backend/
    ├── main.py                     FastAPI app + all routes
    ├── models.py                   Pydantic models (12-D AudioFeatures, etc.)
    ├── similarity.py               Cosine similarity search
    ├── mapping.py                  UMAP 3-D projection (placeholder)
    └── requirements.txt
```

---

## Key Placeholders to Replace

| File | TODO |
|---|---|
| `frontend/app/components/PointCloudViewer.tsx` | Fetch real UMAP points from `/api/py/songs/embed` instead of the random sphere |
| `backend/mapping.py` | Uncomment the real UMAP block; remove the random fallback |
| `backend/main.py` | Replace `SONG_VECTORS` in-memory dict with a real vector DB |
| `backend/main.py` | Add Spotify OAuth flow and call `spotipy` to fetch real audio features |
| `backend/similarity.py` | Swap brute-force loop for FAISS index for scalable ANN search |

## API Reference

### `GET /health`
Returns `{ "status": "ok" }`. Called by the frontend on page load to verify connectivity.

### `POST /songs/embed`
```json
{
  "tracks": [{ "track_id": "...", "tempo": 120, "energy": 0.8, ... }]
}
```
Returns `{ "points": [{ "track_id": "...", "x": 1.2, "y": -3.4, "z": 0.7 }] }`.

### `POST /songs/recommend`
```json
{ "song_id": "song_42", "top_k": 5 }
```
Returns `{ "query_id": "song_42", "recommendations": [...], "scores": [...] }`.
