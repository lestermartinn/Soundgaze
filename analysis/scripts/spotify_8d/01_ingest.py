"""
Data Ingestion
=======================
Loads spotify_songs.csv, cleans it, and produces three versions of the
feature matrix that downstream scripts can import without re-reading the CSV.

Outputs (all written to analysis/data/):
  features_raw.npz     -- original values, no scaling
  features_minmax.npz  -- MinMaxScaler per feature → [0, 1]
  features_unit.npz    -- L2-normalized rows (matches backend vector representation)
  genres_onehot.npz    -- one-hot encoded genre columns (N, 6), unweighted
  metadata.csv         -- track_id, name, artist, genre for plot labeling

Run from the analysis/ directory:
  python 01_ingest.py

Or from anywhere by setting CSV_PATH:
  CSV_PATH=../backend/data/spotify_songs.csv python 01_ingest.py
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, normalize

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ANALYSIS_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ANALYSIS_DIR / "data"
CSV_PATH = Path(os.getenv("CSV_PATH", ANALYSIS_DIR / "../backend/data/spotify_songs.csv"))

# ---------------------------------------------------------------------------
# Feature columns 
# ---------------------------------------------------------------------------

CURRENT_FEATURE_COLS = [
    "danceability",
    "energy",
    "loudness",
    "speechiness",
    "instrumentalness",
    "liveness",
    "valence",
    "tempo",
]

DROPPED_FEATURE_COLS = [
    "acousticness",
    "key",
    "mode",
    "duration_ms",
]

ALL_FEATURE_COLS = CURRENT_FEATURE_COLS + DROPPED_FEATURE_COLS

METADATA_COLS = [
    "track_id",
    "track_name",
    "track_artist",
    "playlist_genre",
]

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"ERROR: CSV not found at {path.resolve()}", file=sys.stderr)
        sys.exit(1)
    print(f"Reading {path.resolve()} ...")
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

def clean(df: pd.DataFrame) -> pd.DataFrame:
    n_raw = len(df)

    # Keep only the columns we need
    keep = [c for c in METADATA_COLS + ALL_FEATURE_COLS if c in df.columns]
    df = df[keep].copy()

    # Drop rows missing any current feature (same as backend)
    df = df.dropna(subset=[c for c in CURRENT_FEATURE_COLS if c in df.columns])

    # Drop duplicate tracks (keep first occurrence)
    df = df.drop_duplicates(subset=["track_id"])

    df = df.reset_index(drop=True)
    print(f"Cleaned: {n_raw} raw rows → {len(df)} unique tracks "
          f"({n_raw - len(df)} dropped)")
    return df


# ---------------------------------------------------------------------------
# Build feature matrices
# ---------------------------------------------------------------------------

def build_matrices(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (raw, minmax, unit) arrays, each shape (N, len(CURRENT_FEATURE_COLS)).

    raw    -- original float values straight from the CSV
    minmax -- MinMaxScaler fit on these N rows, output in [0, 1]
    unit   -- L2-normalized rows of minmax (unit vectors, matches backend)
    """
    raw = df[CURRENT_FEATURE_COLS].to_numpy(dtype=np.float32)

    scaler = MinMaxScaler()
    minmax = scaler.fit_transform(raw).astype(np.float32)

    unit = normalize(minmax, norm="l2").astype(np.float32)

    return raw, minmax, unit


def build_genre_onehot(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """
    One-hot encode playlist_genre.

    Returns
    -------
    onehot : np.ndarray, shape (N, n_genres), dtype float32
        Each row has exactly one 1.0, rest 0.0. Unweighted -- downstream
        scripts apply a genre_weight scalar before combining with audio features.
    genre_labels : list[str]
        Column names in the same order as the onehot columns (sorted for stability).
    """
    dummies = pd.get_dummies(df["playlist_genre"]).astype(np.float32)
    genre_labels = sorted(dummies.columns.tolist())
    return dummies[genre_labels].to_numpy(dtype=np.float32), genre_labels


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_outputs(
    df: pd.DataFrame,
    raw: np.ndarray,
    minmax: np.ndarray,
    unit: np.ndarray,
    genre_onehot: np.ndarray,
    genre_labels: list[str],
) -> None:
    DATA_DIR.mkdir(exist_ok=True)

    np.savez_compressed(DATA_DIR / "features_raw.npz",    features=raw,          cols=CURRENT_FEATURE_COLS)
    np.savez_compressed(DATA_DIR / "features_minmax.npz", features=minmax,       cols=CURRENT_FEATURE_COLS)
    np.savez_compressed(DATA_DIR / "features_unit.npz",   features=unit,         cols=CURRENT_FEATURE_COLS)
    np.savez_compressed(DATA_DIR / "genres_onehot.npz",   features=genre_onehot, cols=genre_labels)
    print(f"Saved feature matrices  (shape: {raw.shape[0]} tracks × {raw.shape[1]} features)")
    print(f"Saved genres_onehot     (shape: {genre_onehot.shape[0]} tracks × {genre_onehot.shape[1]} genres: {genre_labels})")

    meta_cols = [c for c in METADATA_COLS if c in df.columns]
    df[meta_cols].to_csv(DATA_DIR / "metadata.csv", index=False)
    print(f"Saved metadata          ({meta_cols})")


# ---------------------------------------------------------------------------
# Summary printout
# ---------------------------------------------------------------------------

def print_summary(df: pd.DataFrame, raw: np.ndarray) -> None:
    print("\n--- Feature summary (raw values) ---")
    summary = df[CURRENT_FEATURE_COLS].describe().T[["min", "max", "mean", "std"]]
    print(summary.to_string())

    print("\n--- Dropped features present in CSV ---")
    present = [c for c in DROPPED_FEATURE_COLS if c in df.columns]
    missing = [c for c in DROPPED_FEATURE_COLS if c not in df.columns]
    print(f"  Present : {present}")
    if missing:
        print(f"  Missing : {missing}")

    if "playlist_genre" in df.columns:
        print("\n--- Genre distribution ---")
        print(df["playlist_genre"].value_counts().to_string())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    df = load_csv(CSV_PATH)
    df = clean(df)
    raw, minmax, unit = build_matrices(df)
    genre_onehot, genre_labels = build_genre_onehot(df)
    save_outputs(df, raw, minmax, unit, genre_onehot, genre_labels)
    print_summary(df, raw)
    print("\nDone. Run 02_feature_analysis.py next.")


if __name__ == "__main__":
    main()
