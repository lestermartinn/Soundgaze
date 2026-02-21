# Hacklytics 2025 — Hackathon Boilerplate

> Explore your musical DNA as coordinates in an interactive 3-D universe. Find your **Topological Twins** — songs from different corners of the world that share nearly identical audio fingerprints.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind CSS |
| 3-D Rendering | Three.js via `@react-three/fiber` + `@react-three/drei` |
| Backend | FastAPI (Python 3.11+) |
| Vector DB | Actian VectorAI DB (gRPC, HNSW index, COSINE similarity) |
| ML — Mapping | UMAP 3-D reduction (`umap-learn`) |
| Spotify Data | `spotipy` |

---

## Quick Start

See [`docs/SETUP.md`](docs/SETUP.md) for the full walkthrough. Short version:

### 1. Vector DB (Docker)

```bash
cd backend
docker compose up -d
# pulls williamimoh/actian-vectorai-db:1.0b and starts it on port 50051
```

### 2. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate

# Install the Actian Python client (not on PyPI -- one-time)
# Clone it somewhere outside this project, then install the .whl
cd ~
git clone https://github.com/hackmamba-io/actian-vectorAI-db-beta
cd ~/path/to/Hacklytics/backend
pip install ~/actian-vectorAI-db-beta/actiancortex-0.1.0b1-py3-none-any.whl

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### 3. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

App: `http://localhost:3000` — Next.js proxies `/api/py/*` to `localhost:8000`.

---

## Project Structure

```
Hacklytics/
├── docs/
│   └── SETUP.md                    Full setup walkthrough
│
├── frontend/
│   ├── next.config.js              Proxies /api/py/* -> localhost:8000
│   ├── tailwind.config.ts          Custom design tokens
│   ├── package.json
│   └── app/
│       ├── layout.tsx
│       ├── globals.css             Tailwind directives + base styles
│       ├── page.tsx                Home page: health check + recommendation sidebar
│       └── components/
│           └── PointCloudViewer.tsx  Three.js canvas, OrbitControls, click handler
│
└── backend/
    ├── docker-compose.yml          Runs the Actian VectorAI DB container
    ├── main.py                     FastAPI app + routes (add yours here)
    ├── db.py                       Actian VectorAI DB client + helper functions
    ├── models.py                   Pydantic models: AudioFeatures (12-D), requests/responses
    ├── mapping.py                  UMAP 3-D projection placeholder
    ├── similarity.py               Cosine similarity reference (superseded by vector DB)
    └── requirements.txt
```

---

## Adding a New Route

**1. Add a Pydantic model in `backend/models.py`:**
```python
class MyRequest(BaseModel):
    song_id: str

class MyResponse(BaseModel):
    result: str
```

**2. Add a DB helper in `backend/db.py`** (use `search_similar` as reference):
```python
async def my_db_query(song_id: str) -> dict:
    client = get_db()
    # ... call client.search(), client.get(), client.upsert(), etc.
```

**3. Add a route in `backend/main.py`** (use `/songs/recommend` as reference):
```python
@app.post("/my-route", response_model=MyResponse)
async def my_route(body: MyRequest):
    result = await my_db_query(body.song_id)
    return MyResponse(result=result)
```

---

## Key TODOs

| File | What to implement |
|---|---|
| `backend/mapping.py` | Uncomment the real UMAP block |
| `backend/main.py` | Add Spotify OAuth + audio feature ingestion route |
| `frontend/app/components/PointCloudViewer.tsx` | Fetch real UMAP points from `/api/py/songs/embed` |

## API Reference

### `GET /health`
Liveness probe called by the frontend on page load.
```json
{ "status": "ok", "version": "0.1.0" }
```

### `POST /songs/recommend`
Find top-k Topological Twins for a given song.
```json
// Request
{ "song_id": "song_42", "top_k": 5 }

// Response
{ "query_id": "song_42", "recommendations": ["song_7", ...], "scores": [0.98, ...] }
```
