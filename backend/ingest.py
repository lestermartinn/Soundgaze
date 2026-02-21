"""
Dataset ingestion -- loads the Spotify dataset into the Actian VectorAI DB.

Called automatically on startup via main.py lifespan.
Skipped if the DB is already populated (set FORCE_REINGEST=true to override).

"""

import logging
import math
import os
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from db import get_db, COLLECTION, song_id_to_int


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

    Safe to call on every startup -- exits early if data is already present.
    """
    from db import get_db, COLLECTION

    client = get_db()
    count = await client.count(COLLECTION)

    if count > 0 and not FORCE_REINGEST:
        logger.info(
            "DB already contains %d vectors -- skipping ingest. "
            "Set FORCE_REINGEST=true to wipe and re-ingest.",
            count,
        )
        return

    if FORCE_REINGEST and count > 0:
        logger.warning("FORCE_REINGEST=true -- clearing existing vectors before re-ingest.")
        # TODO: uncomment once you confirm the recreate_collection signature
        # await client.recreate_collection(COLLECTION, dimension=DIMENSION, ...)

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

    await _batch_upsert(tracks)

    final_count = await client.count(COLLECTION)
    logger.info("Ingest complete -- DB now contains %d vectors.", final_count)


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
    "key",
    "loudness",
    "mode",
    "speechiness",
    "acousticness",
    "instrumentalness",
    "liveness",
    "valence",
    "tempo",
]

_KEEP_COLS = _METADATA_COLS + _FEATURE_COLS

# Helper function to fill key if value is -1 (no key detected)
def _impute_key(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace key == -1 (undetected) with an imputed integer in [0, 11].

    Strategy: per-genre mode, falling back to global mode.
    """
    unknown_mask = df["key"] == -1
    n_unknown = unknown_mask.sum()
    if n_unknown == 0:
        return df

    # Treat -1 as NaN so mode() ignores it
    df["key"] = df["key"].where(df["key"] != -1, other=pd.NA)

    global_mode = int(df["key"].mode().iloc[0])

    def genre_mode(group: pd.Series) -> pd.Series:
        valid = group.dropna()
        fill = int(valid.mode().iloc[0]) if not valid.empty else global_mode
        return group.fillna(fill)

    if "playlist_genre" in df.columns:
        df["key"] = df.groupby("playlist_genre", group_keys=False)["key"].apply(genre_mode)

    # Any still-NaN rows (e.g. genre also missing) get the global mode
    df["key"] = df["key"].fillna(global_mode).astype(float)

    logger.info("Imputed key for %d rows (per-genre mode, global fallback=%d).", n_unknown, global_mode)
    return df


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
    df = _impute_key(df)
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
    Min-max scale every feature column to [0, 1] so each has equal weight in
    the vector embedding. Fit is done on the full dataset (not per-row).
    """
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(df[_FEATURE_COLS])
    return pd.DataFrame(scaled, columns=_FEATURE_COLS, index=df.index)


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
