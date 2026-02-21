"""
Hacklytics -- FastAPI backend

Add your routes below. Use /songs/recommend as a reference for the full pattern:
  1. Define a Pydantic request/response model in models.py
  2. Pull the DB client via get_db() or use the helper functions in db.py
  3. Call the Actian VectorAI DB and return a typed response
"""

import logging
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import init_db, close_db, search_similar, get_song_vector, sample_song_pool, upsert_song, get_song
from ingest import ingest_if_needed
from models import (
    RecommendRequest,
    RecommendResponse,
    SongPoolRequest,
    SongPoolResponse,
    SongUpsertRequest,
    SongGetResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()          # connect to DB, ensure collection exists
    await ingest_if_needed() # load Kaggle dataset if DB is empty
    yield
    await close_db()         # gracefully close gRPC connection


app = FastAPI(
    title="Hacklytics API",
    description="ML backend for the 3-D musical taste explorer.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Liveness probe -- do not remove, the frontend calls this on page load
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}


# ---------------------------------------------------------------------------
# SAMPLE ROUTE -- use this as a reference when adding new routes
#
# Pattern:
#   1. Declare typed request + response models in models.py
#   2. Fetch or look up a vector using a db.py helper
#   3. Query the DB (search_similar, upsert_song, etc.)
#   4. Return a typed Pydantic response
# ---------------------------------------------------------------------------

@app.post("/songs/recommend", response_model=RecommendResponse)
async def recommend(body: RecommendRequest):
    """Find top-k Topological Twins for a song via Actian VectorAI DB cosine search."""
    query_vector = await get_song_vector(body.song_id)

    if query_vector is None:
        raise HTTPException(status_code=404, detail=f"Song '{body.song_id}' not found in DB.")

    candidate_k = min(max(body.top_k * 3, body.top_k + 5), 200)
    candidates = await search_similar(query_vector=query_vector, top_k=candidate_k)

    filtered: list[dict] = []
    seen_track_ids: set[str] = set()
    for item in candidates:
        track_id = str(item.get("track_id", ""))
        score = float(item.get("score", 0.0))

        if not track_id or track_id == body.song_id:
            continue
        if score >= 1.0:
            continue
        if track_id in seen_track_ids:
            continue

        seen_track_ids.add(track_id)
        filtered.append(item)
        if len(filtered) >= body.top_k:
            break

    return RecommendResponse(
        query_id=body.song_id,
        recommendations=[r["track_id"] for r in filtered],
        scores=[r["score"] for r in filtered],
    )


@app.post("/songs/pool", response_model=SongPoolResponse)
async def song_pool(body: SongPoolRequest):
    """Return up to 1000 points with new-user fallback.

    - If user_id has songs in DB, include personal songs + random global songs.
    - If user_id is new or omitted (no Spotify link), return random songs so UI still renders.
    """
    sampled = await sample_song_pool(
        user_id=body.user_id,
        user_song_count=body.user_song_count,
        total_count=body.total_count,
    )
    return SongPoolResponse(
        user_songs=sampled["user_songs"],
        global_songs=sampled["global_songs"],
        user_songs_returned=len(sampled["user_songs"]),
        global_songs_returned=len(sampled["global_songs"]),
        total_returned=len(sampled["user_songs"]) + len(sampled["global_songs"]),
        is_new_user=bool(sampled["is_new_user"]),
    )


@app.post("/songs", response_model=SongGetResponse)
async def put_song(body: SongUpsertRequest):
    """Insert/update a single song in the vector DB and return stored record."""
    await upsert_song(
        track_id=body.track_id,
        vector=body.vector,
        name=body.name,
        artist=body.artist,
        genre=body.genre,
        user_id=body.user_id,
    )
    stored = await get_song(body.track_id)
    if stored is None:
        raise HTTPException(status_code=500, detail="Song upsert completed but read-back failed.")
    return SongGetResponse(**stored)


@app.get("/songs/{song_id}", response_model=SongGetResponse)
async def fetch_song(song_id: str):
    """Get a single song by track_id."""
    stored = await get_song(song_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"Song '{song_id}' not found in DB.")
    return SongGetResponse(**stored)


# ---------------------------------------------------------------------------
# Add your routes here
# ---------------------------------------------------------------------------
