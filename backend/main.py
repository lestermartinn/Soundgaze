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

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import init_db, close_db, search_similar, get_song_vector, get_db, COLLECTION_3D, sample_song_pool, upsert_song, get_song
from ingest import ingest_if_needed
from models import (
    RecommendRequest,
    RecommendResponse,
    SongPoolRequest,
    SongPoolResponse,
    SongUpsertRequest,
    SongGetResponse,
    SpotifyImportRequest,
    SpotifySyncResponse,
    SimilarResponse,
    SimilarSong,
    SimilarRequest
)
from spotify import SpotifyImporter


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
# Debug
# ---------------------------------------------------------------------------

@app.get("/debug/songs_3d")
async def debug_songs_3d(n: int = 5):
    """Return n sample points from songs_3d (searches with a zero vector)."""
    client = get_db()
    results = await client.search(COLLECTION_3D, query=[0.0, 0.0, 0.0], top_k=n, with_payload=True, with_vectors=True)
    return [
        {
            "track_id": r.payload.get("track_id"),
            "name":     r.payload.get("name"),
            "artist":   r.payload.get("artist"),
            "genre":    r.payload.get("genre"),
            "user_ids": r.payload.get("user_ids"),
            "xyz":      list(r.vector) if r.vector else None,
            "score":    round(r.score, 4),
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# Point cloud
# ---------------------------------------------------------------------------

@app.get("/songs/3d/all")
async def get_all_songs_3d():
    """
    Return every point in the songs_3d collection with both coordinate sets.

    Each item includes:
      xyz_raw     -- raw UMAP coords (accurate topology)
      xyz_uniform -- quantile-normalized coords (uniform distribution)
      track_id, name, artist, genre
    """
    client = get_db()
    total = await client.count(COLLECTION_3D)
    if total == 0:
        return []

    results = await client.search(
        COLLECTION_3D,
        query=[0.0, 0.0, 0.0],
        top_k=total,
        with_payload=True,
    )
    return [
        {
            "track_id":   r.payload.get("track_id"),
            "name":       r.payload.get("name"),
            "artist":     r.payload.get("artist"),
            "genre":      r.payload.get("genre"),
            "xyz_raw":     r.payload.get("xyz_raw"),
            "xyz_uniform": r.payload.get("xyz_uniform"),
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------

@app.get("/debug/songs_3d")
async def debug_songs_3d(n: int = 5):
    """Return n sample points from songs_3d (searches with a zero vector)."""
    client = get_db()
    results = await client.search(COLLECTION_3D, query=[0.0, 0.0, 0.0], top_k=n, with_payload=True, with_vectors=True)
    return [
        {
            "track_id": r.payload.get("track_id"),
            "name":     r.payload.get("name"),
            "artist":   r.payload.get("artist"),
            "genre":    r.payload.get("genre"),
            "user_ids": r.payload.get("user_ids"),
            "xyz":      list(r.vector) if r.vector else None,
            "score":    round(r.score, 4),
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# Point cloud
# ---------------------------------------------------------------------------

@app.get("/songs/3d/all")
async def get_all_songs_3d():
    """
    Return every point in the songs_3d collection with both coordinate sets.

    Each item includes:
      xyz_raw     -- raw UMAP coords (accurate topology)
      xyz_uniform -- quantile-normalized coords (uniform distribution)
      track_id, name, artist, genre
    """
    client = get_db()
    total = await client.count(COLLECTION_3D)
    if total == 0:
        return []

    results = await client.search(
        COLLECTION_3D,
        query=[0.0, 0.0, 0.0],
        top_k=total,
        with_payload=True,
    )
    return [
        {
            "track_id":   r.payload.get("track_id"),
            "name":       r.payload.get("name"),
            "artist":     r.payload.get("artist"),
            "genre":      r.payload.get("genre"),
            "xyz_raw":     r.payload.get("xyz_raw"),
            "xyz_uniform": r.payload.get("xyz_uniform"),
        }
        for r in results
    ]


@app.post("/songs/spotify/sync", response_model=SpotifySyncResponse)
async def sync_spotify_library(body: SpotifyImportRequest):
    """
    Sync user's top Spotify tracks to local database.

    Fetches up to 50 of the user's most-listened tracks from Spotify,
    converts their audio features to vectors, and adds them to the database.
    If a song already exists, the user_id is merged into the user_ids list.

    Args:
        body.user_id: App user ID to associate with these songs
        body.access_token: Spotify OAuth access token
        body.limit: Number of top songs to fetch (default 50)

    Returns:
        Summary of songs added, merged, and any failures
    """
    try:
        importer = SpotifyImporter(body.access_token)
        tracks = await importer.get_tracks_with_vectors(limit=body.limit)

        songs_added = 0
        songs_merged = 0
        failed_count = 0
        added_tracks = []
        merged_tracks = []

        for track in tracks:
            try:
                track_id = track["track_id"]
                vector = track["vector"]
                name = track["name"]
                artist = track["artist"]

                # Check if song already exists
                existing = await get_song(track_id)
                
                # Upsert with user_id (handles merge internally)
                await upsert_song(
                    track_id=track_id,
                    vector=vector,
                    name=name,
                    artist=artist,
                    genre=None,  # Spotify doesn't provide genre at track level
                    user_id=body.user_id,
                )

                if existing is None:
                    songs_added += 1
                    added_tracks.append(track_id)
                else:
                    # Check if user was already in the list
                    existing_user_ids = existing.get("user_ids", [])
                    if body.user_id not in existing_user_ids:
                        songs_merged += 1
                        merged_tracks.append(track_id)

            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to process track {track.get('track_id', 'unknown')}: {e}")
                failed_count += 1

        total_processed = len(tracks)

        return SpotifySyncResponse(
            user_id=body.user_id,
            songs_added=songs_added,
            songs_merged=songs_merged,
            total_processed=total_processed,
            failed_count=failed_count,
            added_tracks=added_tracks,
            merged_tracks=merged_tracks,
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to sync Spotify library: {str(e)}"
        )
'''
@app.post("/songs/similar", response_model=SimilarResponse)
async def similar(body: SimilarRequest):
    """Return the k most similar songs to a given 12D feature vector via Actian VectorAI cosine search."""
    results = await search_similar(query_vector=body.vector, top_k=body.k)

    return SimilarResponse(
        results=[
            SimilarSong(track_id=r["track_id"], score=r["score"])
            for r in results
        ]
    ) # do not use SimilarResponse(results = result) for validation using SimilarSong model
'''
from typing import Any

@app.get("/songs/{song_id}/similar")
async def get_similar_songs(song_id: str, n: int = 10) -> Any:
    song = await get_song(song_id)
    if not song:
        raise HTTPException(status_code=404, detail=f"Song '{song_id}' not found.")
    
    vector_8d = song.get("vector")
    if not vector_8d:
        raise HTTPException(status_code=404, detail=f"No vector found for song '{song_id}'.")

    similar = await search_similar(query_vector=vector_8d, top_k=n * 3)  # fetch extra to account for deduplication

    client = get_db()
    results = []
    seen_ids = {song_id}  # pre-seed with the query song so it's never included

    for s in similar:
        track_id = s.get("track_id")
        if not track_id or track_id in seen_ids:
            continue

        seen_ids.add(track_id)
        result = {**s}

        try:
            vector_3d, payload_3d = await client.get(COLLECTION_3D, id=song_id_to_int(track_id))
            if vector_3d:
                result["vector_3d"] = list(vector_3d)
                result["xyz_raw"] = (payload_3d or {}).get("xyz_raw")
                result["xyz_uniform"] = (payload_3d or {}).get("xyz_uniform")
        except Exception as e:
            logging.getLogger(__name__).debug(f"No 3D record for '{track_id}': {e}")

        results.append(result)
        if len(results) >= n:
            break

    return {"songs": results}