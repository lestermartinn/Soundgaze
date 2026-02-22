"""
Vector DB module -- wraps Actian VectorAI DB (AsyncCortexClient).

Infrastructure (do not modify):
  - init_db / close_db  managed by FastAPI lifespan in main.py

Helper functions:
  - search_similar()    SAMPLE -- shows the full call pattern, use as reference
  - Add your own helpers below the sample section

DB setup (one-time per machine):
  1. git clone https://github.com/hackmamba-io/actian-vectorAI-db-beta
  2. pip install actian-vectorAI-db-beta/actiancortex-0.1.0b1-py3-none-any.whl
  3. cd backend && docker compose up -d
"""

import hashlib
import logging
import os
import random
from collections import defaultdict

try:
    from cortex import AsyncCortexClient, DistanceMetric
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "Missing Actian VectorAI client module 'cortex'. "
        "Install the Actian wheel (not the deprecated PyPI package 'cortex-client'): "
        "pip install <path-to>/actiancortex-0.1.0b1-py3-none-any.whl"
    ) from exc

logger = logging.getLogger(__name__)

VECTOR_DB_URL: str = os.getenv("VECTOR_DB_URL", "localhost:50051")
COLLECTION: str = "songs"        # 8-D audio feature vectors
COLLECTION_3D: str = "songs_3d"  # 3-D UMAP projections for the point cloud
DIMENSION: int = 8    # must match len(_FEATURE_COLS) in ingest.py
DIMENSION_3D: int = 3

_client: AsyncCortexClient | None = None
_user_song_index: dict[str, set[str]] = defaultdict(set)


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

def get_db() -> AsyncCortexClient:
    """Return the live client. Only valid after init_db() has run."""
    if _client is None:
        raise RuntimeError("Vector DB not initialised. Did lifespan run?")
    return _client

# TODO: adjust to fit our actual song embedding
def song_id_to_int(song_id: str) -> int:
    """Deterministically map a string song ID to a positive 31-bit integer DB key."""
    return int(hashlib.md5(song_id.encode()).hexdigest(), 16) % (2 ** 31)


async def init_db() -> None:
    """Open the gRPC connection, ensure the collection exists, seed if empty."""
    global _client
    _client = AsyncCortexClient(VECTOR_DB_URL, pool_size=1)  # TODO: change pool_size for production
    _client._pool_config.keepalive_time_ms = 600_000  # 10 min -- prevents "too many pings" throttle
    await _client.__aenter__()

    version, uptime = await _client.health_check()
    logger.info("Connected to Actian VectorAI DB %s (uptime %ss)", version, uptime)

    for name, dim in [(COLLECTION, DIMENSION), (COLLECTION_3D, DIMENSION_3D)]:
        if not await _client.has_collection(name):
            logger.info("Creating collection '%s' (dim=%d, metric=COSINE)", name, dim)
            await _client.create_collection(
                name=name,
                dimension=dim,
                distance_metric=DistanceMetric.COSINE,
                hnsw_m=16,
                hnsw_ef_construct=200,
                hnsw_ef_search=50,
            )
        count = await _client.count(name)
        logger.info("Collection '%s' ready -- %d vectors stored.", name, count)


async def reset_collections() -> None:
    """Drop and recreate both Kaggle song collections.

    Used by FORCE_REINGEST to get a clean HNSW index -- FAISS HNSW degrades
    badly when vectors are updated in-place (marks old as deleted, adds new),
    causing hangs after ~3k updates on an existing index.

    NOTE: this wipes all data in songs and songs_3d, including any user songs.
    """
    client = get_db()
    for name, dim in [(COLLECTION, DIMENSION), (COLLECTION_3D, DIMENSION_3D)]:
        if await client.has_collection(name):
            await client.delete_collection(name)
            logger.info("Dropped collection '%s'.", name)
        await client.create_collection(
            name=name,
            dimension=dim,
            distance_metric=DistanceMetric.COSINE,
            hnsw_m=16,
            hnsw_ef_construct=200,
            hnsw_ef_search=50,
        )
        logger.info("Recreated collection '%s' (dim=%d).", name, dim)


async def close_db() -> None:
    """Gracefully close the gRPC connection."""
    global _client
    if _client is not None:
        await _client.__aexit__(None, None, None)
        _client = None
        logger.info("Vector DB connection closed.")


# ---------------------------------------------------------------------------
# SAMPLE helper -- use this as a reference when adding new DB helpers
#
# Pattern:
#   1. Call get_db() to get the live AsyncCortexClient
#   2. Use client methods: search(), upsert(), batch_upsert(), get(), count(), etc.
#   3. Map integer IDs back to string track_ids via result.payload["track_id"]
#   4. Return plain dicts or dataclasses (not raw cortex objects) to keep routes clean
# ---------------------------------------------------------------------------

async def search_similar(query_vector: list[float], top_k: int = 5) -> list[dict]:
    """Return top_k songs closest to query_vector by COSINE similarity."""
    client = get_db()
    results = await client.search(COLLECTION, query=query_vector, top_k=top_k, with_payload=True)
    return [
        {
            "track_id": r.payload.get("track_id", str(r.id)),
            "name":     r.payload.get("name"),
            "artist":   r.payload.get("artist"),
            "genre":    r.payload.get("genre"),
            "score":    round(r.score, 4),
        }
        for r in results
    ]


async def get_song_vector(song_id: str) -> list[float] | None:
    """Retrieve a stored vector by string song ID. Returns None if not found."""
    client = get_db()
    try:
        vector, _payload = await client.get(COLLECTION, id=song_id_to_int(song_id))
        return list(vector) if vector else None
    except Exception:
        return None


def _coerce_user_id(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return str(value)


def _coerce_user_ids(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            uid = _coerce_user_id(item)
            if uid and uid not in seen:
                seen.add(uid)
                result.append(uid)
        return result
    uid = _coerce_user_id(value)
    return [uid] if uid else []


def _merge_user_ids(existing_ids: list[str], new_user_id: str | None) -> list[str]:
    if not new_user_id:
        return existing_ids
    if new_user_id in existing_ids:
        return existing_ids
    return [*existing_ids, new_user_id]


def _add_user_song_index(track_id: str, user_ids: list[str]) -> None:
    for uid in user_ids:
        _user_song_index[uid].add(track_id)


async def _get_song_record(track_id: str) -> dict | None:
    client = get_db()
    try:
        vector, payload = await client.get(COLLECTION, id=song_id_to_int(track_id))
        payload = payload or {}

        user_ids = _coerce_user_ids(payload.get("user_ids"))
        primary_user_id = _coerce_user_id(payload.get("user_id"))
        if primary_user_id and primary_user_id not in user_ids:
            user_ids = [primary_user_id, *user_ids]

        record = {
            "track_id": str(payload.get("track_id", track_id)),
            "vector": list(vector),
            "name": payload.get("name"),
            "artist": payload.get("artist"),
            "genre": payload.get("genre"),
            "user_id": user_ids[0] if user_ids else None,
            "user_ids": user_ids,
        }
        _add_user_song_index(record["track_id"], user_ids)
        return record
    except Exception:
        return None


async def sample_song_pool(
    user_id: str | None = None,
    user_song_count: int = 100,
    total_count: int = 1000,
) -> dict[str, object]:
    """Sample random songs with user-aware fallback.

    Behavior:
      - If user_id is provided, try to include up to user_song_count songs for that user.
      - Fill the remaining slots with random global songs (user_id is null).
      - If user has no songs (new user) or user_id is omitted, return random global songs.
    """
    client = get_db()
    if total_count <= 0:
        return {
            "user_songs": [],
            "global_songs": [],
            "is_new_user": bool(user_id),
        }

    desired_user_count = min(max(user_song_count, 0), total_count) if user_id else 0

    selected_user: list[dict] = []
    selected_user_ids: set[str] = set()
    if user_id:
        indexed_track_ids = list(_user_song_index.get(user_id, set()))
        random.shuffle(indexed_track_ids)
        for track_id in indexed_track_ids:
            if len(selected_user) >= desired_user_count:
                break
            song = await _get_song_record(track_id)
            if song is None:
                continue
            if user_id in song.get("user_ids", []):
                selected_user.append({
                    "track_id": song["track_id"],
                    "name": song.get("name"),
                    "artist": song.get("artist"),
                    "genre": song.get("genre"),
                    "user_id": song.get("user_id"),
                    "user_ids": song.get("user_ids", []),
                })
                selected_user_ids.add(song["track_id"])

    unique_by_track_id: dict[str, dict] = {}
    attempts = 0
    max_attempts = 120
    top_k_per_attempt = min(max(total_count, 300), 1000)

    while attempts < max_attempts:
        attempts += 1
        query_vector = [random.random() for _ in range(DIMENSION)]
        results = await client.search(COLLECTION, query=query_vector, top_k=top_k_per_attempt, with_payload=True)

        for r in results:
            payload = r.payload or {}
            track_id = str(payload.get("track_id", r.id))
            if track_id not in unique_by_track_id:
                payload_user_ids = _coerce_user_ids(payload.get("user_ids"))
                payload_user_id = _coerce_user_id(payload.get("user_id"))
                if payload_user_id and payload_user_id not in payload_user_ids:
                    payload_user_ids = [payload_user_id, *payload_user_ids]

                unique_by_track_id[track_id] = {
                    "track_id": track_id,
                    "name": payload.get("name"),
                    "artist": payload.get("artist"),
                    "genre": payload.get("genre"),
                    "user_id": payload_user_ids[0] if payload_user_ids else None,
                    "user_ids": payload_user_ids,
                }
                _add_user_song_index(track_id, payload_user_ids)

        # Stop early once we have a healthy candidate pool.
        if len(unique_by_track_id) >= max(total_count * 5, 3000):
            break

    songs = list(unique_by_track_id.values())
    random.shuffle(songs)

    user_songs_all = [s for s in songs if user_id and user_id in s.get("user_ids", []) and s["track_id"] not in selected_user_ids]
    global_songs_all = [s for s in songs if s["user_id"] is None]
    other_user_songs = [s for s in songs if s["user_id"] is not None and (not user_id or user_id not in s.get("user_ids", []))]

    needed_user = max(0, desired_user_count - len(selected_user))
    if needed_user > 0 and user_songs_all:
        selected_user.extend(random.sample(user_songs_all, min(needed_user, len(user_songs_all))))
    remaining = total_count - len(selected_user)

    selected_global = random.sample(global_songs_all, min(remaining, len(global_songs_all)))
    remaining -= len(selected_global)

    # Fallback if global pool is smaller than requested total.
    if remaining > 0 and other_user_songs:
        selected_global.extend(random.sample(other_user_songs, min(remaining, len(other_user_songs))))

    has_user_songs = len(selected_user) > 0 or len(user_songs_all) > 0

    return {
        "user_songs": selected_user,
        "global_songs": selected_global,
        "is_new_user": bool(user_id) and not has_user_songs,
    }


async def upsert_song(
    track_id: str,
    vector: list[float],
    name: str | None = None,
    artist: str | None = None,
    genre: str | None = None,
    user_id: str | None = None,
) -> None:
    """Insert or update a song vector + payload by string track_id."""
    client = get_db()
    existing = await _get_song_record(track_id)
    existing_user_ids = existing.get("user_ids", []) if existing else []
    merged_user_ids = _merge_user_ids(existing_user_ids, _coerce_user_id(user_id))

    payload = {
        "track_id": track_id,
        "name": name,
        "artist": artist,
        "genre": genre,
        "user_id": merged_user_ids[0] if merged_user_ids else None,
        "user_ids": merged_user_ids,
    }
    await client.upsert(COLLECTION, id=song_id_to_int(track_id), vector=vector, payload=payload)
    _add_user_song_index(track_id, merged_user_ids)


async def get_song(track_id: str) -> dict | None:
    """Fetch a full song record (vector + payload) by string track_id."""
    return await _get_song_record(track_id)


# ---------------------------------------------------------------------------
# songs_3d helpers
# ---------------------------------------------------------------------------

async def upsert_song_3d(track_id: str, vector_3d: list[float], payload: dict) -> None:
    """Write a single 3-D song point into the songs_3d collection."""
    client = get_db()
    await client.upsert(
        COLLECTION_3D,
        id=song_id_to_int(track_id),
        vector=vector_3d,
        payload=payload,
    )


async def batch_upsert_3d(tracks: list[dict], batch_size: int = 500) -> None:
    """
    Write 3-D UMAP vectors to songs_3d in chunks.

    Each element of `tracks`:
      {"track_id": str, "vector": list[float] (len=3), "payload": dict}
    """
    import math

    def _is_valid(v: list[float]) -> bool:
        return all(math.isfinite(x) for x in v)

    client = get_db()
    total_batches = -(-len(tracks) // batch_size)
    skipped = 0

    for i in range(0, len(tracks), batch_size):
        batch = [t for t in tracks[i : i + batch_size] if _is_valid(t["vector"])]
        skipped += (batch_size - len(batch))
        batch_num = i // batch_size + 1

        if not batch:
            logger.warning("3D batch %d/%d -- all records invalid, skipping.", batch_num, total_batches)
            continue

        seen: set[int] = set()
        deduped = []
        for t in batch:
            int_id = song_id_to_int(t["track_id"])
            if int_id not in seen:
                seen.add(int_id)
                deduped.append(t)
        batch = deduped

        ids      = [song_id_to_int(t["track_id"]) for t in batch]
        vectors  = [t["vector"] for t in batch]
        payloads = [t["payload"] for t in batch]

        try:
            await client.batch_upsert(COLLECTION_3D, ids=ids, vectors=vectors, payloads=payloads)
            logger.info("3D batch %d/%d -- upserted %d tracks.", batch_num, total_batches, len(batch))
        except Exception as exc:
            logger.warning("3D batch %d/%d failed (%s) -- falling back to per-record upsert.", batch_num, total_batches, exc)
            for t in batch:
                try:
                    await client.upsert(COLLECTION_3D, id=song_id_to_int(t["track_id"]), vector=t["vector"], payload=t["payload"])
                except Exception as e:
                    logger.warning("Skipping 3D track '%s': %s", t["track_id"], e)
                    skipped += 1

    if skipped:
        logger.warning("3D ingest -- total skipped: %d", skipped)