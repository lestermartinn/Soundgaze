# Hacklytics Session Context

## Project
Music discovery app. FastAPI backend + Next.js frontend + Actian VectorAI DB (cortex, gRPC, FAISS/HNSW).

## Current State (as of 2026-02-21)
Backend ingest is working. FORCE_REINGEST runs correctly after adding `reset_collections()`.
DB is populated with 28,356 songs (8D vectors + 3D UMAP projections).

## Collections
- `songs` — 8D audio feature vectors (for similarity search)
- `songs_3d` — 3D UMAP projections (for point cloud visualization)

## Feature Columns (8D)
```python
_FEATURE_COLS = [
    "danceability", "energy", "loudness", "speechiness",
    "instrumentalness", "liveness", "valence", "tempo",
]
```
Dropped: `mode`, `key`, `acousticness`. L2 normalized after MinMaxScaler.

## songs_3d Payload Structure
Each point stores BOTH coordinate sets:
```json
{
  "track_id": "...", "name": "...", "artist": "...", "genre": "...",
  "user_ids": [],
  "xyz_raw": [x, y, z],      // raw UMAP output (accurate topology)
  "xyz_uniform": [x, y, z]   // quantile-normalized (uniform distribution)
}
```
The vector itself = xyz_uniform (used for ANN search).

## Key DB Config (db.py)
```python
DIMENSION = 8
DIMENSION_3D = 3
_client = AsyncCortexClient(VECTOR_DB_URL, pool_size=1)
_client._pool_config.keepalive_time_ms = 600_000  # prevents "too many pings"
```

## FORCE_REINGEST Fix
HNSW index hangs if you upsert into existing collection (~3k updates).
Solution: `reset_collections()` drops + recreates both collections before ingest.
Ingest uses `INGEST_BATCH_SIZE=100` env var (default 500 caused ping throttle at batch 48).

## UMAP Config (mapping.py)
```python
umap.UMAP(n_components=3, n_neighbors=40, min_dist=0.4, spread=3.0,
          metric="cosine", n_epochs=300, random_state=42)
```
Followed by QuantileTransformer(output_distribution="uniform").
Saves: `data/umap_model.pkl` + `data/quantile_model.pkl`.
`fit_umap()` returns `(raw_embedding, uniform_embedding)` tuple.

## Existing Endpoints
- `GET /songs/3d/all` — fetches all 28k points (too heavy for frontend, use sample instead)
- `GET /debug/songs_3d` — debug: returns n sample 3D points

## Point Cloud Design (NOT YET IMPLEMENTED)
### Backend needed:
- `GET /songs/3d?n=1000&user_id=optional` — sample_song_pool but returns 3D coords
  - Uses existing `sample_song_pool()` in db.py logic
  - Returns `{ global_sample: [{track_id, name, artist, xyz_raw, xyz_uniform}], user_songs: [{...}] }`
- `GET /songs/{track_id}/similar?n=10` — click handler:
  1. Look up 8D vector from `songs` collection
  2. Run cosine ANN search in `songs`
  3. Fetch 3D coords for results from `songs_3d`
  4. Return similar songs with xyz coords for highlighting

### Frontend needed:
- New `/explore` page
- Stack: `@react-three/fiber` + `@react-three/drei`
- Three point types:
  - Global sample → gray/dim
  - User songs → teal/bright
  - Recommended neighbors (on click) → orange/accent
- OrbitControls for pan/rotate/zoom
- Click point → info panel (name, artist, genre) + fetch similar
- Checkbox: toggle xyz_uniform ↔ xyz_raw (no re-fetch, just swap coords in geometry)
- Hover tooltip: name + artist

### Data flow:
1. Load: GET /songs/3d?n=1000&user_id=xxx → store both xyz arrays
2. Render 3D geometry with BufferGeometry + Points
3. Checkbox → swap active coord set in geometry
4. Click → GET /songs/{track_id}/similar → highlight neighbors in scene

## Running the Backend
```bash
# Fresh DB (wipes all data):
FORCE_REINGEST=true INGEST_BATCH_SIZE=100 uvicorn main:app --port 8000

# Normal (no reingest):
uvicorn main:app --reload --port 8000

# Docker DB:
docker compose up -d
```

## validate_umap.py
Standalone script — fits UMAP fresh from CSV, shows side-by-side raw vs quantile plot.
Saves to `umap_comparison.png`. Run: `python validate_umap.py` from backend/.
