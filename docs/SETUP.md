# Setup Guide

Follow these steps to get the full stack running locally. You will need two terminal tabs: one for the backend, one for the frontend.

---

## Prerequisites

| Tool | Min Version | Install |
|---|---|---|
| Node.js | 18+ | https://nodejs.org |
| Python | 3.11+ | https://python.org |
| npm | 9+ | Bundled with Node |
| git | any | https://git-scm.com |

Verify you're good before starting:

```bash
node -v
python3 --version
npm -v
```

---

## 1. Clone the repo

```bash
git clone <repo-url>
cd Hacklytics
```

---

## 2. Backend (FastAPI) — Terminal 1

```bash
cd backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# Install Python dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`.
Interactive API docs (Swagger UI): `http://localhost:8000/docs`.

> **Tip:** The `--reload` flag automatically restarts the server when you save a Python file.

---

## 3. Frontend (Next.js) — Terminal 2

```bash
cd frontend

# Install JavaScript dependencies
npm install

# Start the dev server
npm run dev
```

The app will be live at `http://localhost:3000`.

> Next.js is configured to proxy all `/api/py/*` requests to `localhost:8000`, so no CORS setup is needed.

---

## 4. Verify everything is working

1. Open `http://localhost:3000` in your browser.
2. The **dot** next to the app name in the header shows backend status:
   - 🟡 Pulsing yellow → still checking
   - 🟢 Green → backend connected
   - 🔴 Red → backend unreachable (make sure step 2 is running)
3. Click any point in the 3D cloud — a "Topological Twins" panel should appear on the right.
4. You can also hit the backend directly:
   ```bash
   curl http://localhost:8000/health
   # → {"status":"ok","version":"0.1.0"}
   ```

---

## File Structure

```
Hacklytics/
│
├── docs/
│   └── SETUP.md                  ← you are here
│
├── README.md                     High-level project overview + API reference
│
├── frontend/                     Next.js 14 (App Router) + TypeScript
│   ├── next.config.js            Proxy /api/py/* → localhost:8000
│   ├── tailwind.config.ts        Custom design tokens (colors, fonts)
│   ├── postcss.config.js         Wires Tailwind into the build
│   ├── package.json
│   ├── tsconfig.json
│   └── app/
│       ├── layout.tsx            Root HTML shell
│       ├── globals.css           Tailwind directives + base styles
│       ├── page.tsx              Home page — health check + recommendation sidebar
│       └── components/
│           └── PointCloudViewer.tsx   Three.js canvas (1k placeholder points, OrbitControls, click handler)
│
└── backend/                      FastAPI (Python)
    ├── main.py                   All API routes (/health, /songs/embed, /songs/recommend)
    ├── models.py                 Pydantic data models — 12-D AudioFeatures, EmbeddedPoint, request/response shapes
    ├── similarity.py             Cosine similarity search (brute-force placeholder)
    ├── mapping.py                UMAP 3-D projection (placeholder — real code commented in)
    └── requirements.txt          Python dependencies
```

### Key concepts

| Piece | What it does |
|---|---|
| `PointCloudViewer.tsx` | Renders the 3D star-field using `@react-three/fiber`. Each point is a song. Click a point → fires `onPointClick(songId)` up to the page. |
| `page.tsx` | Orchestrates the UI: checks backend health on load, listens for point clicks, fetches recommendations, and shows the sidebar. |
| `main.py` | The single FastAPI entrypoint. All routes live here and delegate to `similarity.py` / `mapping.py`. |
| `models.py` | The 12 Spotify audio features (`tempo`, `energy`, `valence`, etc.) are defined here as a Pydantic model with a `.to_vector()` helper. |
| `mapping.py` | Will call UMAP to squish 12-D audio vectors into (x, y, z). Currently returns random coordinates — uncomment the real block when ready. |
| `similarity.py` | Brute-force cosine similarity. Returns the top-k nearest songs. Swap with FAISS for scale. |

---

## Common Issues

**`ModuleNotFoundError` on backend start**
Make sure your virtual environment is activated (`source .venv/bin/activate`) before running `uvicorn`.

**Red dot / backend unreachable on frontend**
Confirm the backend is running on port 8000. Check for port conflicts:
```bash
lsof -i :8000
```

**`npm install` fails on `umap-learn` / native modules**
`umap-learn` is a Python package — it goes in the backend, not the frontend. Run `pip install -r requirements.txt` inside the `backend/` folder with the venv active.

**Three.js canvas is blank**
Open the browser console. A common cause is React strict mode double-mounting — this is normal in dev and harmless.
