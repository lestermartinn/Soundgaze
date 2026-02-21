"""
Hacklytics — FastAPI backend

Endpoints
---------
GET  /health            Backend liveness check (called by Next.js on load)
POST /songs/embed       12-D features → UMAP 3-D coordinates
POST /songs/recommend   Song ID → top-k Topological Twins via cosine similarity
"""

import random
import math
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import (
    AudioFeatures,
    EmbedRequest,
    EmbedResponse,
    RecommendRequest,
    RecommendResponse,
)
from similarity import find_topological_twins
from mapping import reduce_to_3d

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Hacklytics API",
    description="ML backend for the 3-D musical taste explorer.",
    version="0.1.0",
)

# Allow requests from the Next.js dev server.
# In production, restrict origins to your deployed domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory placeholder dataset
# Swap this with a real DB (Postgres + pgvector, Pinecone, etc.) later.
# ---------------------------------------------------------------------------

def _make_random_vector() -> list[float]:
    """Generate a plausible random 12-D audio feature vector."""
    return [random.random() for _ in range(12)]

SONG_VECTORS: dict[str, list[float]] = {
    f"song_{i}": _make_random_vector() for i in range(1000)
}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Liveness probe — Next.js calls this on page load to confirm connectivity."""
    return {"status": "ok", "version": app.version}


@app.post("/songs/embed", response_model=EmbedResponse)
async def embed_songs(body: EmbedRequest):
    """
    Accept a batch of Spotify audio features and return UMAP 3-D coordinates.

    Real flow:
      1. Normalise each AudioFeatures object into a 12-D vector via .to_vector()
      2. Feed vectors into UMAP (see mapping.py)
      3. Return (x, y, z) per track for Three.js to render
    """
    if not body.tracks:
        raise HTTPException(status_code=400, detail="tracks list must not be empty")

    points = reduce_to_3d(body.tracks)
    return EmbedResponse(points=points)


@app.post("/songs/recommend", response_model=RecommendResponse)
async def recommend(body: RecommendRequest):
    """
    Find the top-k Topological Twins for a given song.

    Real flow:
      1. Look up the query song's 12-D vector (from Spotify API or cache)
      2. Run cosine similarity against all stored vectors (see similarity.py)
      3. Return ordered list of similar song IDs + scores
    """
    query_vector = SONG_VECTORS.get(body.song_id)

    if query_vector is None:
        # Fallback: generate a random vector so the UI stays interactive
        # during development. Remove this branch in production.
        query_vector = _make_random_vector()

    results = find_topological_twins(
        query_vector=query_vector,
        dataset=SONG_VECTORS,
        top_k=body.top_k,
    )

    return RecommendResponse(
        query_id=body.song_id,
        recommendations=[r.song_id for r in results],
        scores=[round(r.score, 4) for r in results],
    )
