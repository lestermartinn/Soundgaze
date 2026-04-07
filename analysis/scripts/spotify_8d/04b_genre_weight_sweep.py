"""
Genre Weight Sweep
=============================================
Tests the 8-feature baseline with genre one-hot columns at a range of weights
to find the best tradeoff between audio similarity preservation (k-NN recall)
and genre cluster cohesion (silhouette).

All runs use UMAP with the same config as the rest of the pipeline.
Ground-truth k-NN is cosine on 8-feature unit vectors throughout.

Outputs
-------
  results/04b_genre_weights.csv
  figures/04_ablation/genre_weight_metrics.png  -- metrics vs weight line chart
  figures/04_ablation/genre_weight_scatter.png  -- point cloud grid (one panel per weight)

Run from analysis/:
  python 04b_genre_weight_sweep.py
"""

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import umap
from sklearn.manifold import trustworthiness
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import LabelEncoder

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANALYSIS_DIR = Path(__file__).parent.parent.parent
DATA_DIR     = ANALYSIS_DIR / "data"
FIG_DIR      = ANALYSIS_DIR / "figures" / "04_ablation"
RESULTS_DIR  = ANALYSIS_DIR / "results"

FEATURE_COLS = [
    "danceability", "energy", "loudness", "speechiness",
    "instrumentalness", "liveness", "valence", "tempo",
]

GENRE_WEIGHTS = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]

SAMPLE_N     = 3000
K_NEIGHBORS  = 10
RANDOM_STATE = 42

UMAP_KWARGS = dict(
    n_components=3,
    metric="cosine",
    n_neighbors=40,
    min_dist=0.4,
    n_epochs=200,
    random_state=RANDOM_STATE,
    verbose=False,
)

GENRE_PALETTE = {
    "edm":   "#1DB954",
    "latin": "#FF6B35",
    "pop":   "#E91E8C",
    "r&b":   "#9B59B6",
    "rap":   "#F1C40F",
    "rock":  "#3498DB",
}

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_data():
    for p in [DATA_DIR / "features_minmax.npz", DATA_DIR / "features_unit.npz",
              DATA_DIR / "genres_onehot.npz", DATA_DIR / "metadata.csv"]:
        if not p.exists():
            print(f"ERROR: {p} not found -- run 01_ingest.py first.", file=sys.stderr)
            sys.exit(1)

    minmax_8     = np.load(DATA_DIR / "features_minmax.npz", allow_pickle=True)["features"]
    unit_8       = np.load(DATA_DIR / "features_unit.npz",   allow_pickle=True)["features"]
    genre_npz    = np.load(DATA_DIR / "genres_onehot.npz",   allow_pickle=True)
    genre_onehot = genre_npz["features"]
    meta         = pd.read_csv(DATA_DIR / "metadata.csv")

    print(f"Loaded {len(minmax_8)} tracks")
    return minmax_8, unit_8, genre_onehot, meta


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_gt_neighbors(unit, idx, k):
    X = unit[idx]
    nn = NearestNeighbors(n_neighbors=k + 1, metric="cosine", n_jobs=-1).fit(X)
    _, nbrs = nn.kneighbors(X)
    return nbrs[:, 1:]


def knn_recall(coords_sub, gt_nbrs, k):
    nn = NearestNeighbors(n_neighbors=k + 1, metric="euclidean", n_jobs=-1).fit(coords_sub)
    _, nbrs = nn.kneighbors(coords_sub)
    nbrs = nbrs[:, 1:]
    return float(np.mean([
        len(set(gt_nbrs[i]) & set(nbrs[i])) / k
        for i in range(len(gt_nbrs))
    ]))


def compute_metrics(unit_sub, coords_sub, gt_nbrs, genre_sub):
    trust  = trustworthiness(unit_sub, coords_sub, n_neighbors=K_NEIGHBORS, metric="cosine")
    recall = knn_recall(coords_sub, gt_nbrs, K_NEIGHBORS)
    sil    = silhouette_score(coords_sub, genre_sub, metric="euclidean",
                              sample_size=1000, random_state=RANDOM_STATE)
    return round(trust, 4), round(recall, 4), round(sil, 4)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def normalize_coords(coords):
    lo = coords.min(axis=0)
    hi = coords.max(axis=0)
    return (coords - lo) / (hi - lo + 1e-9)


def run_weight(weight, minmax_8, genre_onehot, unit_8, sample_idx, gt_nbrs, genre_sub):
    X = np.concatenate([minmax_8, genre_onehot * weight], axis=1) if weight > 0 else minmax_8
    t0 = time.time()
    coords = normalize_coords(umap.UMAP(**UMAP_KWARGS).fit_transform(X).astype(np.float32))
    elapsed = time.time() - t0
    trust, recall, sil = compute_metrics(unit_8[sample_idx], coords[sample_idx], gt_nbrs, genre_sub)
    print(f"  w={weight:<4}  trust={trust}  recall={recall}  sil={sil}  ({elapsed:.1f}s)")
    return coords, {"genre_weight": weight, "trustworthiness": trust,
                    "knn_recall": recall, "silhouette": sil, "time_s": round(elapsed, 1)}


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_metrics(df):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle("Genre Weight vs Metrics (8-feature baseline + genre one-hot × weight)", fontsize=12)

    specs = [
        ("trustworthiness", "Trustworthiness", "#3498DB"),
        ("knn_recall",      "k-NN Recall @10", "#E91E8C"),
        ("silhouette",      "Silhouette (genre)", "#1DB954"),
    ]
    for ax, (col, label, color) in zip(axes, specs):
        ax.plot(df["genre_weight"], df[col], "o-", color=color, linewidth=2, markersize=6)
        ax.set_xlabel("Genre weight")
        ax.set_ylabel(label)
        ax.set_title(label)
        ax.set_xticks(df["genre_weight"])
        for x, y in zip(df["genre_weight"], df[col]):
            ax.annotate(f"{y:.3f}", (x, y), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=7)

    fig.tight_layout()
    out = FIG_DIR / "genre_weight_metrics.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


def plot_scatter_grid(all_coords, weights, meta):
    """4×2 grid of XY scatter plots, one panel per weight, colored by genre."""
    n_cols = 4
    n_rows = 2
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(20, 10))
    axes = axes.flatten()

    rng      = np.random.default_rng(RANDOM_STATE)
    plot_idx = rng.choice(len(meta), size=min(5000, len(meta)), replace=False)

    for ax, coords, w in zip(axes, all_coords, weights):
        c = coords[plot_idx]
        m = meta.iloc[plot_idx].reset_index(drop=True)
        for genre, color in GENRE_PALETTE.items():
            mask = m["playlist_genre"] == genre
            ax.scatter(c[mask, 0], c[mask, 1], c=color, s=1.5, alpha=0.5,
                       label=genre, rasterized=True)
        ax.set_title(f"genre weight = {w}", fontsize=10)
        ax.set_xlabel("dim 1", fontsize=8)
        ax.set_ylabel("dim 2", fontsize=8)
        ax.tick_params(labelsize=7)

    # Single legend on last used axis
    axes[0].legend(markerscale=5, fontsize=7, loc="upper right")

    # Hide unused panels
    for ax in axes[len(weights):]:
        ax.set_visible(False)

    fig.suptitle("Point Cloud — 8 audio features + genre one-hot × weight\n(XY projection, 5k songs)",
                 fontsize=13)
    fig.tight_layout()
    out = FIG_DIR / "genre_weight_scatter.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    minmax_8, unit_8, genre_onehot, meta = load_data()

    rng        = np.random.default_rng(RANDOM_STATE)
    sample_idx = rng.choice(len(minmax_8), size=min(SAMPLE_N, len(minmax_8)), replace=False)
    genre_enc  = LabelEncoder().fit_transform(meta["playlist_genre"])
    genre_sub  = genre_enc[sample_idx]

    print(f"\nComputing ground-truth cosine k-NN (k={K_NEIGHBORS}) on {len(sample_idx)} subsample ...")
    gt_nbrs = compute_gt_neighbors(unit_8, sample_idx, K_NEIGHBORS)

    print(f"\nRunning {len(GENRE_WEIGHTS)} weight configs ...\n")
    results    = []
    all_coords = []

    for w in GENRE_WEIGHTS:
        coords, m = run_weight(w, minmax_8, genre_onehot, unit_8, sample_idx, gt_nbrs, genre_sub)
        results.append(m)
        all_coords.append(coords)

    df = pd.DataFrame(results)
    out_csv = RESULTS_DIR / "04b_genre_weights.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {out_csv}")

    print("\n--- Results ---")
    print(df.to_string(index=False))

    print("\nGenerating plots ...")
    plot_metrics(df)
    plot_scatter_grid(all_coords, GENRE_WEIGHTS, meta)

    # Recommendation
    # Best recall-silhouette tradeoff: highest recall that still has sil > 0.5
    good = df[df["silhouette"] > 0.5]
    if not good.empty:
        rec = good.loc[good["knn_recall"].idxmax()]
        print(f"\nSuggested weight (best recall with silhouette > 0.5): {rec['genre_weight']}"
              f"  recall={rec['knn_recall']}  sil={rec['silhouette']}")
    else:
        rec = df.loc[df["knn_recall"].idxmax()]
        print(f"\nNo weight achieves sil > 0.5 — best recall at w={rec['genre_weight']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
