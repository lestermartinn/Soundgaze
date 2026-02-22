"""
Hacklytics -- FastAPI backend

Add your routes below. Use /songs/recommend as a reference for the full pattern:
  1. Define a Pydantic request/response model in models.py
  2. Pull the DB client via get_db() or use the helper functions in db.py
  3. Call the Actian VectorAI DB and return a typed response
"""

import logging
import math
import os
import asyncio
import random
from contextlib import asynccontextmanager
from typing import Any

import numpy as np

from dotenv import load_dotenv
load_dotenv()

import google.genai as genai

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from db import init_db, close_db, search_similar, get_song_vector, get_db, COLLECTION_3D, sample_song_pool, upsert_song, upsert_song_3d, get_song, song_id_to_int
from mapping import get_reducer, get_quantiler, normalize_raw_coords
from ingest import ingest_if_needed
from models import (
    RecommendRequest,
    RecommendResponse,
    SongPoolRequest,
    SongPoolResponse,
    SongUpsertRequest,
    SongGetResponse,
    SongDescribeResponse,
    SpotifyImportRequest,
    SpotifySyncResponse,
    SimilarResponse,
    SimilarSong,
    SimilarRequest,
    RandomWalkStep,
    RandomWalkResponse,
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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    """Return up to 1000 points with new-user fallback, enriched with 3D coords.

    - If user_id has songs in DB, include personal songs + random global songs.
    - If user_id is new or omitted (no Spotify link), return random songs so UI still renders.
    - Each song is enriched with xyz_raw/xyz_uniform from COLLECTION_3D; songs
      without a 3D record are dropped.
    """
    sampled = await sample_song_pool(
        user_id=body.user_id,
        user_song_count=body.user_song_count,
        total_count=body.total_count,
    )

    client = get_db()

    async def enrich(song: dict) -> dict | None:
        try:
            _, pay_3d = await client.get(COLLECTION_3D, id=song_id_to_int(song["track_id"]))
            p = pay_3d or {}
            xyz_raw     = p.get("xyz_raw")
            xyz_uniform = p.get("xyz_uniform")
            if not xyz_raw or not xyz_uniform:
                return None
            if not all(math.isfinite(v) for v in xyz_raw + xyz_uniform):
                return None
            return {**song, "xyz_raw": xyz_raw, "xyz_uniform": xyz_uniform}
        except Exception:
            return None

    all_songs    = sampled["user_songs"] + sampled["global_songs"]
    n_user       = len(sampled["user_songs"])
    enriched_all = await asyncio.gather(*[enrich(s) for s in all_songs])

    enriched_user   = [s for s in enriched_all[:n_user]  if s is not None]
    enriched_global = [s for s in enriched_all[n_user:]  if s is not None]

    return SongPoolResponse(
        user_songs=enriched_user,
        global_songs=enriched_global,
        user_songs_returned=len(enriched_user),
        global_songs_returned=len(enriched_global),
        total_returned=len(enriched_user) + len(enriched_global),
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

# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

_gemini_client = None

def _get_gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="GEMINI_API_KEY not set.")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client

@app.get("/songs/describe", response_model=SongDescribeResponse)
async def describe_song(name: str, artist: str, genre: str | None = None):
    """Return a short Gemini-generated cultural description for a song."""
    client = _get_gemini()
    genre_hint = f" ({genre})" if genre else ""
    prompt = (
        f'Write a TWO (2) sentence cultural and musical description of "{name}" by {artist}{genre_hint}. '
        f"Cover the genre, era, cultural significance, and what makes it distinctive. "
        f"Be concise and engaging — no headers or bullet points."
    )
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return SongDescribeResponse(name=name, artist=artist, description=response.text.strip())


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

        client = get_db()

        for track in tracks:
            try:
                track_id = track["track_id"]
                vector   = track["vector"]
                name     = track["name"]
                artist   = track["artist"]

                # ── 8D collection ──────────────────────────────────────────
                existing_8d = await get_song(track_id)
                await upsert_song(
                    track_id=track_id,
                    vector=vector,
                    name=name,
                    artist=artist,
                    genre=None,
                    user_id=body.user_id,
                )
                if existing_8d is None:
                    songs_added += 1
                    added_tracks.append(track_id)
                elif body.user_id not in existing_8d.get("user_ids", []):
                    songs_merged += 1
                    merged_tracks.append(track_id)

                # ── 3D collection ──────────────────────────────────────────
                # Try to load existing 3D record to preserve coords + merge user_ids
                xyz_raw     = None
                xyz_uniform = None
                existing_3d_user_ids: list[str] = []
                try:
                    vec_3d, pay_3d = await client.get(COLLECTION_3D, id=song_id_to_int(track_id))
                    p = pay_3d or {}
                    existing_3d_user_ids = p.get("user_ids", [])
                    xyz_raw     = p.get("xyz_raw")
                    xyz_uniform = p.get("xyz_uniform")
                    if not vec_3d:
                        xyz_raw = xyz_uniform = None
                except Exception:
                    pass  # song not in 3D collection yet

                # Compute 3D coords only if missing
                if not xyz_raw or not xyz_uniform:
                    arr         = np.array([vector], dtype=np.float32)
                    raw_arr     = get_reducer().transform(arr)
                    uni_arr     = get_quantiler().transform(raw_arr)
                    xyz_raw     = [float(v) for v in normalize_raw_coords(raw_arr)[0]]
                    xyz_uniform = [float(v) for v in uni_arr[0]]

                merged_3d_user_ids = list(set(existing_3d_user_ids + [body.user_id]))

                await upsert_song_3d(
                    track_id=track_id,
                    vector_3d=xyz_raw,
                    payload={
                        "track_id":   track_id,
                        "name":       name,
                        "artist":     artist,
                        "xyz_raw":    xyz_raw,
                        "xyz_uniform": xyz_uniform,
                        "user_ids":   merged_3d_user_ids,
                    },
                )

            except Exception as e:
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

        try:
            vector_3d, payload_3d = await client.get(COLLECTION_3D, id=song_id_to_int(track_id))
            if not vector_3d:
                continue
            p = payload_3d or {}
            xyz_raw     = p.get("xyz_raw")
            xyz_uniform = p.get("xyz_uniform")
            if not xyz_raw or not xyz_uniform:
                continue
        except Exception as e:
            logging.getLogger(__name__).debug(f"No 3D record for '{track_id}': {e}")
            continue

        results.append({
            **s,
            "xyz_raw":     xyz_raw,
            "xyz_uniform": xyz_uniform,
        })
        if len(results) >= n:
            break

    return {"songs": results}


@app.get("/songs/{track_id}/prev-url")
async def get_track_prev_url(track_id: str) -> Any:
    """Return Spotify preview URL for a given track_id."""
    song = await get_song(track_id)
    if not song:
        raise HTTPException(status_code=404, detail=f"Song '{track_id}' not found.")

    spotify_url = f"https://open.spotify.com/track/{track_id}"
    return {
        "track_id": track_id,
        "preview_url": spotify_url,
    }


def _choose_weighted_candidate(candidates: list[dict], sample_temperature: float, rng: random.Random) -> dict:
    if len(candidates) == 1:
        return candidates[0]

    safe_temp = max(sample_temperature, 1e-3)
    logits = [float(c.get("score", 0.0)) / safe_temp for c in candidates]
    max_logit = max(logits)
    weights = [math.exp(l - max_logit) for l in logits]
    total_weight = sum(weights)

    if total_weight <= 0 or not math.isfinite(total_weight):
        return rng.choice(candidates)

    return rng.choices(candidates, weights=weights, k=1)[0]


@app.get("/songs/{track_id}/walk", response_model=RandomWalkResponse)
async def random_walk_songs(
    track_id: str,
    steps: int = Query(10, ge=1, le=100),
    k: int = Query(20, ge=2, le=200),
    temperature: float = Query(0.5, ge=0.0, le=1.0),
    restart_prob: float = Query(0.1, ge=0.0, le=1.0),
    no_repeat_window: int = Query(3, ge=1, le=50),
    random_seed: int | None = Query(None),
) -> RandomWalkResponse:
    seed_song = await get_song(track_id)
    if not seed_song:
        raise HTTPException(status_code=404, detail=f"Song '{track_id}' not found.")

    seed_vector = seed_song.get("vector")
    if not seed_vector:
        raise HTTPException(status_code=404, detail=f"No vector found for song '{track_id}'.")

    rng = random.Random(random_seed)
    scaled_temperature = 0.05 + (temperature * 1.95)
    effective_k = max(2, min(k, int(round(2 + (k - 2) * temperature))))
    search_k = min(max(k * 4, k + 10), 500)

    path: list[RandomWalkStep] = [
        RandomWalkStep(
            step=0,
            track_id=track_id,
            name=seed_song.get("name"),
            artist=seed_song.get("artist"),
            genre=seed_song.get("genre"),
            transition_score=None,
            restarted=False,
        )
    ]

    song_cache: dict[str, dict] = {track_id: seed_song}
    current_track_id = track_id
    current_vector = list(seed_vector)

    for step_idx in range(1, steps + 1):
        restarted = False
        if current_track_id != track_id and rng.random() < restart_prob:
            current_track_id = track_id
            current_vector = list(seed_vector)
            restarted = True

        similar = await search_similar(query_vector=current_vector, top_k=search_k)
        recent_window = {item.track_id for item in path[max(0, len(path) - no_repeat_window):]}

        candidates: list[dict] = []
        seen_ids: set[str] = set()

        for item in similar:
            candidate_id = str(item.get("track_id", "")).strip()
            if not candidate_id or candidate_id == current_track_id:
                continue
            if candidate_id in seen_ids:
                continue
            if candidate_id in recent_window:
                continue

            seen_ids.add(candidate_id)
            candidates.append(item)
            if len(candidates) >= k:
                break

        if not candidates:
            immediate_previous = path[-2].track_id if len(path) >= 2 else None
            for item in similar:
                candidate_id = str(item.get("track_id", "")).strip()
                if not candidate_id or candidate_id == current_track_id:
                    continue
                if candidate_id in seen_ids:
                    continue
                if immediate_previous and candidate_id == immediate_previous:
                    continue
                seen_ids.add(candidate_id)
                candidates.append(item)
                if len(candidates) >= k:
                    break

        if not candidates:
            break

        sampled_pool = candidates[:effective_k]
        picked = _choose_weighted_candidate(sampled_pool, scaled_temperature, rng)
        next_track_id = str(picked.get("track_id"))

        if next_track_id not in song_cache:
            cached_song = await get_song(next_track_id)
            if cached_song:
                song_cache[next_track_id] = cached_song

        next_song = song_cache.get(next_track_id, {})
        path.append(
            RandomWalkStep(
                step=step_idx,
                track_id=next_track_id,
                name=next_song.get("name") or picked.get("name"),
                artist=next_song.get("artist") or picked.get("artist"),
                genre=next_song.get("genre") or picked.get("genre"),
                transition_score=float(picked.get("score", 0.0)),
                restarted=restarted,
            )
        )

        next_vector = next_song.get("vector") if next_song else None
        if not next_vector:
            break

        current_track_id = next_track_id
        current_vector = list(next_vector)

    # Fetch 3D coords for all path steps in parallel
    client = get_db()

    async def _fetch_xyz(tid: str) -> tuple[str, list | None, list | None]:
        try:
            _, pay_3d = await client.get(COLLECTION_3D, id=song_id_to_int(tid))
            p = pay_3d or {}
            return tid, p.get("xyz_raw"), p.get("xyz_uniform")
        except Exception:
            return tid, None, None

    xyz_results = await asyncio.gather(*[_fetch_xyz(s.track_id) for s in path])
    xyz_map = {tid: (raw, uni) for tid, raw, uni in xyz_results}

    path = [
        s.model_copy(update={
            "xyz_raw":     xyz_map.get(s.track_id, (None, None))[0],
            "xyz_uniform": xyz_map.get(s.track_id, (None, None))[1],
        })
        for s in path
    ]

    return RandomWalkResponse(
        seed_track_id=track_id,
        steps_requested=steps,
        steps_returned=max(0, len(path) - 1),
        k=k,
        effective_k=effective_k,
        temperature=temperature,
        restart_prob=restart_prob,
        no_repeat_window=no_repeat_window,
        path=path,
    )
