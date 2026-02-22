"""
UMAP dimensionality reduction — converts 8-D audio feature vectors to 3-D (x, y, z).

The model is fit once on the full dataset during ingest and saved to disk.
Subsequent calls (e.g. for user profile vectors) use transform() on the cached model.

A QuantileTransformer is applied after UMAP to spread the 3-D coordinates into a
more uniform distribution — improving the point cloud exploration experience without
affecting similarity relationships (which are computed in 8-D space).

Usage
-----
During ingest (fit on full matrix):
    coords_3d = fit_umap(features_matrix)   # np.ndarray (N, 10) → (N, 3)

For individual vectors (user profiles):
    xyz = reduce_vector(vector_10d)         # list[float] len=10 → len=3
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path

import numpy as np
import umap
from sklearn.preprocessing import QuantileTransformer

logger = logging.getLogger(__name__)

UMAP_MODEL_PATH:     str = os.getenv("UMAP_MODEL_PATH",     "data/umap_model.pkl")
QUANTILE_MODEL_PATH: str = os.getenv("QUANTILE_MODEL_PATH", "data/quantile_model.pkl")

# In-memory cache
_reducer:    umap.UMAP | None           = None
_quantiler:  QuantileTransformer | None = None

def fit_umap(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Fit UMAP on the full feature matrix, apply quantile normalization to spread
    the 3-D coords uniformly, save both models to disk, and return both embeddings.

    Args:
        vectors: np.ndarray of shape (N, 8) -- the scaled feature matrix.

    Returns:
        Tuple of (raw_embedding, uniform_embedding), each shape (N, 3).
        raw_embedding     -- direct UMAP output (accurate topology)
        uniform_embedding -- quantile-normalized (uniform distribution)
    """
    global _reducer, _quantiler
    logger.info("Fitting UMAP on %d vectors (this takes ~30-60 s)...", len(vectors))

    reducer = umap.UMAP(
        n_components=3,
        n_neighbors=40,
        min_dist=0.4,
        spread=3.0,
        metric="cosine",
        n_epochs=300,
        random_state=42,
    )
    raw_embedding = reducer.fit_transform(vectors).astype(np.float32)  
    _reducer = reducer

    # Quantile-normalize each axis independently to a uniform [0, 1] distribution.
    quantiler = QuantileTransformer(output_distribution="uniform", random_state=42)
    uniform_embedding = quantiler.fit_transform(raw_embedding).astype(np.float32)
    _quantiler = quantiler

    Path(UMAP_MODEL_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(UMAP_MODEL_PATH, "wb") as f:
        pickle.dump(reducer, f)
    with open(QUANTILE_MODEL_PATH, "wb") as f:
        pickle.dump(quantiler, f)
    logger.info("UMAP + quantile models saved.")

    return raw_embedding, uniform_embedding

def get_reducer() -> umap.UMAP:
    """Return the cached UMAP reducer, loading from disk if needed."""
    global _reducer
    if _reducer is None:
        if not Path(UMAP_MODEL_PATH).exists():
            raise FileNotFoundError(
                f"UMAP model not found at '{UMAP_MODEL_PATH}'. "
                "Run ingest at least once to create it."
            )
        with open(UMAP_MODEL_PATH, "rb") as f:
            _reducer = pickle.load(f)
        logger.info("Loaded UMAP model from '%s'.", UMAP_MODEL_PATH)
    return _reducer


def get_quantiler() -> QuantileTransformer:
    """Return the cached QuantileTransformer, loading from disk if needed."""
    global _quantiler
    if _quantiler is None:
        if not Path(QUANTILE_MODEL_PATH).exists():
            raise FileNotFoundError(
                f"Quantile model not found at '{QUANTILE_MODEL_PATH}'. "
                "Run ingest at least once to create it."
            )
        with open(QUANTILE_MODEL_PATH, "rb") as f:
            _quantiler = pickle.load(f)
        logger.info("Loaded quantile model from '%s'.", QUANTILE_MODEL_PATH)
    return _quantiler

def reduce_vector(vector_8d: list[float]) -> list[float]:
    """
    Project a single 8-D vector into the 3-D UMAP space with quantile normalization.

    Args:
        vector_8d: Scaled 8-D audio feature vector.

    Returns:
        [x, y, z] as plain Python floats, consistent with songs_3d.
    """
    arr = np.array([vector_8d], dtype=np.float32)
    raw = get_reducer().transform(arr)          # (1, 3)
    uniform = get_quantiler().transform(raw)    # (1, 3)
    return [float(v) for v in uniform[0]]
