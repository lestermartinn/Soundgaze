# Setup Guide

Follow these steps to get the full stack running locally. You will need three terminal tabs: one for the DB, one for the backend, one for the frontend.

---

## Prerequisites

| Tool | Min Version | Install |
|---|---|---|
| Node.js | 18+ | https://nodejs.org |
| Python | 3.11+ | https://python.org |
| Docker Desktop | any | https://docker.com |
| git | any | https://git-scm.com |

---

## 1. Clone the repo

```bash
git clone <repo-url>
cd Hacklytics
```

---

## 2. Get the dataset

The Spotify CSV is not in the repo (too large). Get `spotify_songs.csv` from a teammate and place it at:

```
backend/data/spotify_songs.csv
```

Create the folder if it doesn't exist:

```bash
mkdir -p backend/data
```

---

## 3. Install the Actian VectorAI DB Python client

The client `.whl` is not on PyPI — install it manually once:

```bash
git clone https://github.com/hackmamba-io/actian-vectorAI-db-beta
pip install actian-vectorAI-db-beta/actiancortex-0.1.0b1-py3-none-any.whl
```

---

## 4. Start the vector DB — Terminal 1

```bash
cd Hacklytics/backend
docker compose up -d
```

The DB runs as a Docker container on `localhost:50051`. Data is persisted to `backend/data/` so it survives restarts.

---

## 5. Backend (FastAPI) — Terminal 2

```bash
cd Hacklytics/backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# Install Python dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --port 8000
```

**First run only:** on startup the server detects an empty DB and automatically ingests `spotify_songs.csv` — cleaning, scaling, and uploading all ~28,000 tracks. This takes about 60 seconds. You'll see batch logs like:

```
INFO: Batch 1/57 -- upserted 500 tracks.
INFO: Batch 2/57 -- upserted 500 tracks.
...
INFO: Ingest complete -- DB now contains 28356 vectors.
```

Every subsequent startup skips ingest instantly since the DB is already populated.

The API will be live at `http://localhost:8000`.
Interactive docs (Swagger UI): `http://localhost:8000/docs`.

---

## 6. Frontend (Next.js) — Terminal 3

```bash
cd Hacklytics/frontend
npm install
npm run dev
```

The app will be live at `http://localhost:3000`.

> Next.js proxies all `/api/py/*` requests to `localhost:8000` — no CORS setup needed.

---

## 7. Verify everything is working

1. Open `http://localhost:3000`.
2. The dot next to the app name in the header shows backend status:
   - Yellow pulsing → still checking
   - Green → backend connected
   - Red → backend unreachable (check step 5)
3. Hit the backend directly to confirm:
   ```bash
   curl http://localhost:8000/health
   # → {"status":"ok","version":"0.1.0"}
   ```

---

## Common Issues

**DB container won't start**
Make sure Docker Desktop is running. Then:
```bash
cd backend && docker compose up -d
```

**`ModuleNotFoundError: cortex`**
The `.whl` wasn't installed. See step 3.

**`ModuleNotFoundError` on any other package**
Make sure your venv is activated: `source .venv/bin/activate`

**Ingest fails with `FileNotFoundError`**
`data/spotify_songs.csv` is missing. See step 2.

**Red dot / backend unreachable**
Check the backend is running on port 8000:
```bash
lsof -i :8000
```

**Want to wipe and re-ingest the DB:**
```bash
FORCE_REINGEST=true uvicorn main:app --reload --port 8000
```
