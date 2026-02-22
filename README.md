# Soundgaze (Hacklytics 2026)

Explore music as a 3D universe. Soundgaze maps tracks into a point cloud, lets users inspect nearest-neighbor relationships, and runs controllable random walks through sonically similar songs.

## What this repo contains

- `frontend/`: Next.js 14 app (Spotify auth, 3D viewer, walkthrough UI).
- `backend/`: FastAPI API (Actian VectorAI integration, ingest, similarity, random walk, Gemini descriptions).
- `backend/docker-compose.yml`: local Actian VectorAI DB container.
- `backend/data/`: dataset + persisted vector DB files + saved UMAP artifacts.

## Architecture

- **Frontend**: Next.js + React + Tailwind + `@react-three/fiber` / `three`.
- **Backend**: FastAPI + Pydantic.
- **Vector store**: Actian VectorAI DB over gRPC (`localhost:50051`).
- **Embeddings**:
    - 8D normalized audio-feature vectors in collection `songs`.
    - 3D UMAP coordinates in collection `songs_3d` (`xyz_raw` and `xyz_uniform`).
- **External APIs**:
    - Spotify OAuth + Web API (via NextAuth + `spotipy`).
    - Gemini (`google-genai`) for song description text.

## Prerequisites

- **Windows (PowerShell)** commands are shown below.
- Python 3.11+
- Node.js 18+
- Docker Desktop
- Git

## Environment variables

Create env files before running:

### `frontend/.env.local`

```env
NEXTAUTH_URL=http://127.0.0.1:3000
NEXTAUTH_SECRET=replace-with-a-random-secret

SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Optional: backend base URL used in auth callback sync
API_BASE=http://localhost:8000

# Optional override for frontend API client
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### `backend/.env` (optional, but recommended)

```env
# Optional override; default already points to local docker db
VECTOR_DB_URL=localhost:50051

# Required only for /songs/describe
GEMINI_API_KEY=your_gemini_api_key

# Optional ingest controls
DATASET_PATH=data/spotify_songs.csv
INGEST_BATCH_SIZE=500
FORCE_REINGEST=false
```

## One-time setup

### 1) Start Vector DB

```powershell
Set-Location backend
docker compose up -d
```

### 2) Create backend venv + install deps

```powershell
Set-Location backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3) Install Actian Python wheel (required)

The `cortex` client is not published on PyPI.

```powershell
Set-Location ..
git clone https://github.com/hackmamba-io/actian-vectorAI-db-beta
Set-Location backend
python -m pip install ..\actian-vectorAI-db-beta\actiancortex-0.1.0b1-py3-none-any.whl
```

### 4) Install frontend deps

```powershell
Set-Location ..\frontend
npm install
```

## Run locally

Open 3 terminals.

### Terminal A: Vector DB

```powershell
Set-Location backend
docker compose up -d
```

### Terminal B: Backend API

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Notes:
- On first startup, backend ingest runs if collections are empty.
- This creates UMAP artifacts in `backend/data/` and populates both collections.

### Terminal C: Frontend

```powershell
Set-Location frontend
npm run dev
```

Open:
- App: `http://127.0.0.1:3000`
- FastAPI docs: `http://127.0.0.1:8000/docs`

## Dataset expectations

Default ingest expects:

- `backend/data/spotify_songs.csv`

If your dataset is elsewhere, set `DATASET_PATH` in `backend/.env`.

## Main API endpoints

- `GET /health`: health/version.
- `POST /songs/pool`: fetch point cloud sample for user/global songs.
- `POST /songs/recommend`: top-k nearest neighbors for one track.
- `GET /songs/{song_id}`: fetch song record from 8D collection.
- `GET /songs/{song_id}/similar?n=10`: similar songs enriched with 3D payload when available.
- `GET /songs/{track_id}/walk?...`: random-walk traversal (temperature, restart, no-repeat controls).
- `GET /songs/describe?name=...&artist=...&genre=...`: Gemini-generated short description.
- `POST /songs/spotify/sync`: sync user library from Spotify token.
- `POST /songs/spotify/top-frequent`: import user top tracks by popularity.
- `GET /songs/3d/all`: dump full 3D collection payload.
- `GET /debug/songs_3d?n=5`: debug sample from 3D collection.

## Helpful validation scripts

From `backend/` with venv active:

```powershell
python scripts\smoke_test_backend.py --base-url http://127.0.0.1:8000
python scripts\critical_endpoint_test.py --base-url http://127.0.0.1:8000
python scripts\validate_umap.py
```

## Troubleshooting

### `ModuleNotFoundError: cortex`

Install the Actian `.whl` (see setup step 3). Do not use deprecated `cortex-client` package.

### Backend `Failed to fetch` from frontend

- Confirm backend is running on `127.0.0.1:8000`.
- Confirm `NEXT_PUBLIC_API_URL`/`API_BASE` values.
- Check endpoint-specific requirements:
    - `/songs/describe` requires `GEMINI_API_KEY`.
    - Spotify sync requires valid user token.

### Uvicorn exits immediately

- Make sure you run from `backend/` and the venv is active.
- Verify imports compile:

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
python -m py_compile main.py
```

### Re-ingest from scratch

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
$env:FORCE_REINGEST='true'
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## Key code locations

- Backend entry: `backend/main.py`
- DB client/helpers: `backend/db.py`
- Ingest pipeline: `backend/ingest.py`
- UMAP + normalization: `backend/mapping.py`
- Spotify ingestion: `backend/spotify.py`
- Frontend explore page: `frontend/app/explore/page.tsx`
- 3D renderer: `frontend/app/components/PointCloudViewer.tsx`
- API client (frontend): `frontend/app/lib/api.ts`
- NextAuth Spotify route: `frontend/app/api/auth/[...nextauth]/route.ts`

## Notes for contributors

- Keep vector dimensionality consistent between models and DB helpers when editing ingest/sync flows.
- Prefer adding/adjusting endpoints in `backend/main.py` with typed models in `backend/models.py`.
- If traversal visuals are changed, test both manual and auto-play flow in `frontend/app/explore/page.tsx` + `PointCloudViewer.tsx`.
