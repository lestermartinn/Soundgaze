"""
FMA Setup — Download and inspect FMA metadata.

Downloads fma_metadata.zip (~50MB) if not already present, extracts it,
then prints a summary of available tracks, genres, and feature shapes.

Outputs
-------
data/fma_metadata/          raw CSVs from the zip
data/fma_tracks.parquet     cleaned track index (track_id, title, artist, top_genre, split)
"""

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR     = Path(__file__).parent.parent.parent / "data"
META_DIR     = DATA_DIR / "fma_metadata"
ZIP_PATH     = DATA_DIR / "fma_metadata.zip"
OUT_TRACKS   = DATA_DIR / "fma_tracks.parquet"

DATA_DIR.mkdir(exist_ok=True)

FMA_ZIP_URL = "https://os.unil.cloud.switch.ch/fma/fma_metadata.zip"

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
if not ZIP_PATH.exists():
    print(f"Downloading fma_metadata.zip ...")
    with requests.get(FMA_ZIP_URL, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(ZIP_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):  # 1MB chunks
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    print(f"  {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB", end="\r")
    print(f"\nSaved → {ZIP_PATH}  ({ZIP_PATH.stat().st_size / 1e6:.1f} MB)")
else:
    print(f"Already downloaded: {ZIP_PATH}")

# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------
if not META_DIR.exists() or not any(META_DIR.iterdir()):
    print(f"\nExtracting → {META_DIR} ...")
    META_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for member in zf.infolist():
            # flatten — strip leading directory from zip paths
            name = Path(member.filename).name
            if not name:
                continue
            target = META_DIR / name
            with zf.open(member) as src, open(target, "wb") as dst:
                dst.write(src.read())
    print("Extraction done.")
else:
    print(f"Already extracted: {META_DIR}")

# ---------------------------------------------------------------------------
# Load tracks.csv  (multi-level header)
# ---------------------------------------------------------------------------
print("\n--- tracks.csv ---")
tracks = pd.read_csv(META_DIR / "tracks.csv", index_col=0, header=[0, 1])
print(f"Shape: {tracks.shape}")

# Top-level genre is at ('track', 'genre_top')
genre_col = ("track", "genre_top")
title_col  = ("track", "title")
artist_col = ("artist", "name")
split_col  = ("set", "split")
subset_col = ("set", "subset")

genre_counts = tracks[genre_col].value_counts()
print(f"\nTop-level genre distribution ({tracks[genre_col].notna().sum()} tracks with genre):")
print(genre_counts.to_string())

# ---------------------------------------------------------------------------
# Load echonest.csv
# ---------------------------------------------------------------------------
print("\n--- echonest.csv ---")
echonest_path = META_DIR / "echonest.csv"
if echonest_path.exists():
    echonest = pd.read_csv(echonest_path, index_col=0, header=[0, 1, 2])
    print(f"Shape: {echonest.shape}")
    # Audio features are under ('echonest', 'audio_features', *)
    if ("echonest", "audio_features") in [c[:2] for c in echonest.columns]:
        audio_cols = [c for c in echonest.columns if c[1] == "audio_features"]
        print(f"Audio feature columns ({len(audio_cols)}): {[c[2] for c in audio_cols]}")
    null_pct = echonest.isnull().mean().mean() * 100
    print(f"Overall null%: {null_pct:.1f}%")
    print(f"Valid tracks: {echonest.dropna().shape[0]}")
else:
    print("echonest.csv not found — may be named differently in zip")
    print("Files present:", [f.name for f in META_DIR.iterdir()])

# ---------------------------------------------------------------------------
# Load features.csv  (pre-extracted librosa)
# ---------------------------------------------------------------------------
print("\n--- features.csv ---")
features_path = META_DIR / "features.csv"
if features_path.exists():
    features = pd.read_csv(features_path, index_col=0, header=[0, 1, 2])
    print(f"Shape: {features.shape}  →  {features.shape[1]}D feature vector")
    top_groups = features.columns.get_level_values(0).unique().tolist()
    print(f"Feature groups: {top_groups}")
    null_pct = features.isnull().mean().mean() * 100
    print(f"Overall null%: {null_pct:.1f}%")
else:
    print("features.csv not found")

# ---------------------------------------------------------------------------
# Compute shared track set (echonest ∩ features ∩ has genre)
# ---------------------------------------------------------------------------
print("\n--- Track alignment ---")
if echonest_path.exists() and features_path.exists():
    has_genre  = set(tracks.index[tracks[genre_col].notna()])
    has_echo   = set(echonest.dropna().index)
    has_feat   = set(features.dropna().index)
    shared     = has_genre & has_echo & has_feat
    print(f"Tracks with genre:              {len(has_genre)}")
    print(f"Tracks with full echonest:      {len(has_echo)}")
    print(f"Tracks with full features:      {len(has_feat)}")
    print(f"Intersection (usable for both): {len(shared)}")

    shared_genres = tracks.loc[list(shared), genre_col].value_counts()
    print(f"\nGenre distribution in shared set:")
    print(shared_genres.to_string())

# ---------------------------------------------------------------------------
# Save cleaned track index
# ---------------------------------------------------------------------------
print(f"\n--- Saving track index → {OUT_TRACKS} ---")
track_index = tracks[[genre_col, title_col, artist_col, split_col, subset_col]].copy()
track_index.columns = ["genre", "title", "artist", "split", "subset"]
track_index.index.name = "track_id"
track_index = track_index[track_index["genre"].notna()]
track_index.to_parquet(OUT_TRACKS)
print(f"Saved {len(track_index)} tracks with genre labels.")

print("\nSetup complete. Ready for 10b (sparse baseline) and 10c (rich features).")
