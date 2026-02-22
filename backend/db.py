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

from cortex import AsyncCortexClient, DistanceMetric

logger = logging.getLogger(__name__)

VECTOR_DB_URL: str = os.getenv("VECTOR_DB_URL", "localhost:50051")
COLLECTION: str = "songs"        # 11-D audio feature vectors
COLLECTION_3D: str = "songs_3d"  # 3-D UMAP projections for the point cloud
DIMENSION: int = 8    # must match len(_FEATURE_COLS) in ingest.py
DIMENSION_3D: int = 3

_client: AsyncCortexClient | None = None


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
    _client = AsyncCortexClient(VECTOR_DB_URL, pool_size=1) # TODO: change pool size for production
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
        point = await client.get(COLLECTION, id=song_id_to_int(song_id))
        return list(point.vector) if point else None
    except Exception:
        return None


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