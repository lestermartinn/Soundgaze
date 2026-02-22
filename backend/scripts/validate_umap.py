"""
validate_umap.py -- offline validation of the UMAP reduction quality.

Metrics
-------
1. Trustworthiness  (sklearn) -- how well local neighborhoods are preserved [0, 1]
2. k-NN recall                -- fraction of 8-D neighbors recovered in 3-D
3. Visual comparison          -- raw UMAP vs quantile-normalized, coloured by energy

Fits UMAP fresh from the CSV -- does NOT require the DB or saved pickle files.

Run from backend/:
    python validate_umap.py
"""

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.manifold import trustworthiness
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler, normalize, QuantileTransformer
import matplotlib.pyplot as plt
import umap

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATASET_PATH = Path("data/spotify_songs.csv")

K         = 15    # neighbors to check
N_SAMPLE  = 5000  # subsample for expensive metrics (full 28k is slow)
RAND_SEED = 42

FEATURE_COLS = [
    "danceability", "energy", "loudness",
    "speechiness", "instrumentalness",
    "liveness", "valence", "tempo",
]

COLOR_FEATURE = "energy"

# UMAP params -- mirrors mapping.py
UMAP_PARAMS = dict(
    n_components=3,
    n_neighbors=40,
    min_dist=0.4,
    spread=3.0,
    metric="cosine",
    n_epochs=300,
    random_state=42,
)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # ---- Load CSV + scale -------------------------------------------------
    print(f"Reading {DATASET_PATH} ...")
    df = pd.read_csv(DATASET_PATH)
    df = df.dropna(subset=FEATURE_COLS).drop_duplicates(subset=["track_id"]).reset_index(drop=True)

    X = normalize(MinMaxScaler().fit_transform(df[FEATURE_COLS]), norm="l2").astype(np.float32)
    print(f"  {len(X)} tracks loaded ({X.shape[1]}-D)")

    # ---- Fit UMAP ---------------------------------------------------------
    print(f"\nFitting UMAP (this takes ~30-60 s) ...")
    reducer = umap.UMAP(**UMAP_PARAMS)
    X_raw = reducer.fit_transform(X).astype(np.float32)
    print(f"  Raw embedding shape: {X_raw.shape}")

    # ---- Apply quantile normalization -------------------------------------
    quantiler = QuantileTransformer(output_distribution="uniform", random_state=42)
    X_q = quantiler.fit_transform(X_raw).astype(np.float32)
    print("  Quantile normalization applied.")

    # ---- Subsample for expensive metrics ----------------------------------
    rng = np.random.default_rng(RAND_SEED)
    idx = rng.choice(len(X), size=min(N_SAMPLE, len(X)), replace=False)
    X_s, X_raw_s = X[idx], X_raw[idx]

    # ---- 1. Trustworthiness -----------------------------------------------
    print(f"\n[1] Trustworthiness  (k={K}, n={len(idx)} points)")
    tw = trustworthiness(X_s, X_raw_s, n_neighbors=K, metric="cosine")
    print(f"    Score : {tw:.4f}")
    print(f"    Interp: {'GOOD (>0.85)' if tw > 0.85 else 'OK (>0.70)' if tw > 0.70 else 'POOR'}")

    # ---- 2. k-NN recall ---------------------------------------------------
    print(f"\n[2] k-NN recall  (k={K}, n={len(idx)} points)")
    nn_8d = NearestNeighbors(n_neighbors=K + 1, metric="cosine",    algorithm="brute").fit(X_s)
    nn_3d = NearestNeighbors(n_neighbors=K + 1, metric="euclidean", algorithm="auto" ).fit(X_raw_s)
    _, nbrs_8d = nn_8d.kneighbors(X_s)
    _, nbrs_3d = nn_3d.kneighbors(X_raw_s)

    recalls = [len(set(nbrs_8d[i, 1:]) & set(nbrs_3d[i, 1:])) / K for i in range(len(X_s))]
    mean_recall = float(np.mean(recalls))
    print(f"    Mean recall@{K} : {mean_recall:.4f}")
    print(f"    Interp         : {'GOOD (>0.70)' if mean_recall > 0.70 else 'OK (>0.50)' if mean_recall > 0.50 else 'POOR'}")

    # ---- 3. Visual comparison: raw vs quantile ----------------------------
    color_values = df[COLOR_FEATURE].values
    print(f"\n[3] Rendering side-by-side: raw UMAP vs quantile-normalized (coloured by '{COLOR_FEATURE}') ...")
    _plot_comparison(X_raw, X_q, color_values, COLOR_FEATURE)


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def _plot_comparison(X_raw: np.ndarray, X_q: np.ndarray, color_values: np.ndarray, feature_name: str) -> None:
    fig = plt.figure(figsize=(18, 7))

    for col, (X, title) in enumerate([
        (X_raw, "Raw UMAP (no quantile)"),
        (X_q,   "UMAP + Quantile Normalized"),
    ], start=1):
        ax = fig.add_subplot(1, 2, col, projection="3d")
        sc = ax.scatter(X[:, 0], X[:, 1], X[:, 2],
                        c=color_values, cmap="viridis", s=1, alpha=0.4)
        plt.colorbar(sc, ax=ax, label=feature_name, shrink=0.5)
        ax.set_title(title)
        ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_zlabel("z")

    fig.suptitle(f"UMAP 3-D projection — coloured by {feature_name}", fontsize=13)
    plt.tight_layout()
    out = Path("umap_comparison.png")
    plt.savefig(out, dpi=150)
    print(f"    Saved to {out.resolve()}")
    plt.show()


if __name__ == "__main__":
    main()
