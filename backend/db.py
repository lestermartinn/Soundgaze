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
COLLECTION: str = "songs"
DIMENSION: int = 11   # must match len(_FEATURE_COLS) in ingest.py

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
    _client = AsyncCortexClient(VECTOR_DB_URL)
    await _client.__aenter__()

    version, uptime = await _client.health_check()
    logger.info("Connected to Actian VectorAI DB %s (uptime %ss)", version, uptime)

    if not await _client.has_collection(COLLECTION):
        logger.info("Creating collection '%s' (dim=%d, metric=COSINE)", COLLECTION, DIMENSION)
        await _client.create_collection(
            name=COLLECTION,
            dimension=DIMENSION,
            distance_metric=DistanceMetric.COSINE,
            hnsw_m=16,
            hnsw_ef_construct=200,
            hnsw_ef_search=50,
        )

    count = await _client.count(COLLECTION)
    logger.info("Collection '%s' ready -- %d vectors stored.", COLLECTION, count)


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
# Add your DB helpers here
# ---------------------------------------------------------------------------
