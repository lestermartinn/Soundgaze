"""
Dataset ingestion -- loads the Spotify dataset into the Actian VectorAI DB.

Called automatically on startup via main.py lifespan.
Skipped if the DB is already populated (set FORCE_REINGEST=true to override).

"""

import logging
import math
import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, normalize
from db import get_db, COLLECTION, COLLECTION_3D, song_id_to_int, batch_upsert_3d
from mapping import fit_umap


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config -- override via environment variables
# ---------------------------------------------------------------------------

# Path to spotify_songs.csv (relative to where uvicorn runs, i.e. backend/)
DATASET_PATH: str = os.getenv("DATASET_PATH", "data/spotify_songs.csv")

# Set FORCE_REINGEST=true to wipe and re-ingest even if the DB has data
FORCE_REINGEST: bool = os.getenv("FORCE_REINGEST", "false").lower() == "true"

# Rows sent to the DB per batch_upsert call (tune for memory vs. speed)
BATCH_SIZE: int = int(os.getenv("INGEST_BATCH_SIZE", "500"))


# ---------------------------------------------------------------------------
# Entry point -- called from main.py lifespan
# ---------------------------------------------------------------------------

async def ingest_if_needed() -> None:
    """
    Load and store the Spotify dataset only when the DB is empty.

    Checks each collection independently:
      - songs     empty → full ingest (load CSV, clean, scale, upsert 11-D)
      - songs_3d  empty → run UMAP on existing 11-D vectors and upsert 3-D

    Safe to call on every startup.
    """
    client = get_db()
    count_11d = await client.count(COLLECTION)
    count_3d  = await client.count(COLLECTION_3D)

    need_11d = count_11d == 0 or FORCE_REINGEST
    need_3d  = count_3d  == 0 or FORCE_REINGEST

    if not need_11d and not need_3d:
        logger.info(
            "Both collections populated (songs=%d, songs_3d=%d) -- skipping ingest. "
            "Set FORCE_REINGEST=true to wipe and re-ingest.",
            count_11d, count_3d,
        )
        return

    if FORCE_REINGEST and (count_11d > 0 or count_3d > 0):
        logger.warning("FORCE_REINGEST=true -- re-ingesting all collections.")

    # We always need the tracks list (either to upsert 11-D, or to build 3-D coords)
    df = _load_dataset(DATASET_PATH)
    logger.info("Loaded %d raw rows.", len(df))

    features_df, metadata_df = _clean(df)
    features_df = _scale_features(features_df)
    logger.info("Features scaled to [0, 1].")

    feature_rows = features_df.to_dict(orient="records")
    metadata_rows = metadata_df.to_dict(orient="records")
    tracks = [
        t
        for feat, meta in zip(feature_rows, metadata_rows)
        if (t := _create_payload(feat, meta)) is not None
    ]
    logger.info("Normalized %d tracks (skipped %d rows).", len(tracks), len(feature_rows) - len(tracks))

    # --- 11-D upsert ---
    if need_11d:
        await _batch_upsert(tracks)
        final_count = await client.count(COLLECTION)
        logger.info("Ingest complete -- songs now contains %d vectors.", final_count)
    else:
        logger.info("songs already has %d vectors -- skipping 11-D upsert.", count_11d)

    # --- 3-D reduction ---
    if need_3d:
        logger.info("Running UMAP to reduce %d tracks to 3-D...", len(tracks))
        feature_matrix = np.array([t["vector"] for t in tracks], dtype=np.float32)
        coords_raw, coords_uniform = fit_umap(feature_matrix)  # each (N, 3)

        tracks_3d = [
            {
                "track_id": t["track_id"],
                "vector":   [float(coords_uniform[i, 0]), float(coords_uniform[i, 1]), float(coords_uniform[i, 2])],
                "payload":  {
                    **t["payload"],
                    "user_ids":    [],
                    "xyz_raw":     [float(coords_raw[i, 0]),     float(coords_raw[i, 1]),     float(coords_raw[i, 2])],
                    "xyz_uniform": [float(coords_uniform[i, 0]), float(coords_uniform[i, 1]), float(coords_uniform[i, 2])],
                },
            }
            for i, t in enumerate(tracks)
        ]

        await batch_upsert_3d(tracks_3d)

        final_count_3d = await client.count(COLLECTION_3D)
        logger.info("3-D ingest complete -- songs_3d now contains %d vectors.", final_count_3d)
    else:
        logger.info("songs_3d already has %d vectors -- skipping 3-D upsert.", count_3d)


# ---------------------------------------------------------------------------
# Step 1: Load raw CSV from disk
# ---------------------------------------------------------------------------

def _load_dataset(path: str) -> pd.DataFrame:
    """Read spotify_songs.csv and return a DataFrame."""
    logger.info("Reading CSV from '%s'...", path)
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# Step 2: Clean the DataFrame
# ---------------------------------------------------------------------------

_METADATA_COLS = [
    "track_id",
    "track_name",
    "track_artist",
    "playlist_genre",
]

_FEATURE_COLS = [
    "danceability",
    "energy",
    "loudness",
    "speechiness",
    "instrumentalness",
    "liveness",
    "valence",
    "tempo",
]

_KEEP_COLS = _METADATA_COLS + _FEATURE_COLS
def _clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Clean the raw DataFrame and split into two aligned DataFrames.

    Returns
    -------
    features_df : pd.DataFrame
        One row per track, columns = _FEATURE_COLS (floats ready to vectorize).
    metadata_df : pd.DataFrame
        Same rows in the same order, columns = _METADATA_COLS.

    TODO: add any extra filtering (e.g. outlier removal).
    """
    original_size = len(df)
    df = df[[c for c in _KEEP_COLS if c in df.columns]].copy()
    df = df.dropna(subset=[c for c in _FEATURE_COLS if c in df.columns])
    df = df.drop_duplicates(subset=["track_id"])
    df = df.reset_index(drop=True)

    logger.info("Cleaned %d rows. %d rows remaining.", original_size - len(df), len(df))

    features_df = df[[c for c in _FEATURE_COLS if c in df.columns]]
    metadata_df = df[[c for c in _METADATA_COLS if c in df.columns]]

    return features_df, metadata_df


# ---------------------------------------------------------------------------
# Step 3: Scale features to [0, 1]
# ---------------------------------------------------------------------------

def _scale_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Min-max scale every feature column to [0, 1] (equal weight per feature),
    then L2-normalize each row to unit magnitude (consistent with cosine similarity).
    """
    scaled = MinMaxScaler().fit_transform(df[_FEATURE_COLS])
    unit   = normalize(scaled, norm="l2")
    return pd.DataFrame(unit, columns=_FEATURE_COLS, index=df.index)


# ---------------------------------------------------------------------------
# Step 4: Normalize a single row
# ---------------------------------------------------------------------------

def _create_payload(features: dict, metadata: dict) -> dict | None:
    """
    Combine one (already-scaled) feature row and one metadata row into a
    DB-ready dict.

    Returns
    -------
    dict with:
      "track_id" : str            -- string ID used to derive the integer DB key
      "payload"  : dict           -- metadata stored alongside the vector
      "vector"   : list[float]    -- 11-D scaled audio feature vector
    """
    try:
        return {
            "track_id": metadata["track_id"],
            "payload": {
                "track_id":   metadata["track_id"],
                "name":       metadata.get("track_name"),
                "artist":     metadata.get("track_artist"),
                "genre":      metadata.get("playlist_genre"),
            },
            "vector": [float(features[col]) for col in _FEATURE_COLS],
        }
    except (KeyError, ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Step 4: Batch-upsert into the DB
# ---------------------------------------------------------------------------

def _is_valid_vector(vector: list[float]) -> bool:
    """Return False if the vector contains any NaN or infinite values."""
    return all(math.isfinite(v) for v in vector)


async def _batch_upsert(tracks: list[dict]) -> None:
    """
    Send normalized tracks to the DB in chunks of BATCH_SIZE.

    Each element of `tracks` is the output of _create_payload():
      {"track_id": str, "vector": list[float], "payload": dict}

    Invalid vectors (NaN/inf) are skipped. If a batch fails, falls back to
    individual upserts so one bad record can't abort the whole ingest.
    """
    client = get_db()
    total_batches = -(-len(tracks) // BATCH_SIZE)  # ceiling division
    skipped = 0

    for i in range(0, len(tracks), BATCH_SIZE):
        batch = [t for t in tracks[i : i + BATCH_SIZE] if _is_valid_vector(t["vector"])]
        skipped += (BATCH_SIZE - len(batch))
        batch_num = i // BATCH_SIZE + 1

        if not batch:
            logger.warning("Batch %d/%d -- all records invalid, skipping.", batch_num, total_batches)
            continue

        # Deduplicate by integer ID within the batch (hash collisions)
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
            await client.batch_upsert(COLLECTION, ids=ids, vectors=vectors, payloads=payloads)
            logger.info("Batch %d/%d -- upserted %d tracks.", batch_num, total_batches, len(batch))
        except Exception as exc:
            logger.warning("Batch %d/%d failed (%s) -- falling back to per-record upsert.", batch_num, total_batches, exc)
            for t in batch:
                try:
                    await client.upsert(COLLECTION, id=song_id_to_int(t["track_id"]), vector=t["vector"], payload=t["payload"])
                except Exception as e:
                    logger.warning("Skipping track '%s': %s", t["track_id"], e)
                    skipped += 1

    if skipped:
        logger.warning("Total skipped during upsert: %d", skipped)
