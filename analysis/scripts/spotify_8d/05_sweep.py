"""
UMAP Hyperparameter Sweep
=============================================
Sweeps UMAP n_neighbors × min_dist × metric to find the best 3D layout
using the final feature set: 8 audio features + genre one-hot × 0.1.

Ground-truth k-NN is always cosine on 8-feature L2-normalised vectors.

Grid
----
  n_neighbors : [10, 20, 40, 80]
  min_dist    : [0.05, 0.1, 0.25, 0.4, 0.8]
  metric      : [cosine, euclidean, correlation]
  Total       : 60 configs

Input
-----
  data/features_minmax.npz  -- 8-feature MinMax-scaled matrix
  data/features_unit.npz    -- L2-normalised unit vectors (ground-truth k-NN)
  data/genres_onehot.npz    -- (N, 6) one-hot genre matrix

Output
------
  results/05_sweep.csv
  figures/05_sweep/heatmap_trust.png   -- trustworthiness heatmap per metric
  figures/05_sweep/heatmap_recall.png  -- k-NN recall heatmap per metric
  figures/05_sweep/heatmap_combined.png -- avg(trust, recall) heatmap per metric

Run from analysis/:
  python 05_sweep.py
"""

import itertools
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
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
FIG_DIR      = ANALYSIS_DIR / "figures" / "05_sweep"
RESULTS_DIR  = ANALYSIS_DIR / "results"

FEATURE_COLS = [
    "danceability", "energy", "loudness", "speechiness",
    "instrumentalness", "liveness", "valence", "tempo",
]

GENRE_WEIGHT = 0.1   # confirmed in Phase 4b

N_NEIGHBORS_GRID = [10, 20, 40, 80]
MIN_DIST_GRID    = [0.05, 0.1, 0.25, 0.4, 0.8]
METRIC_GRID      = ["cosine", "euclidean", "correlation"]

SAMPLE_N     = 3000
K_NEIGHBORS  = 10
RANDOM_STATE = 42

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

    # Final feature matrix: audio + genre × weight
    X = np.concatenate([minmax_8, genre_onehot * GENRE_WEIGHT], axis=1)

    print(f"Loaded {len(minmax_8)} tracks  |  input shape: {X.shape}")
    return X, unit_8, meta


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


def normalize_coords(coords):
    lo = coords.min(axis=0)
    hi = coords.max(axis=0)
    return (coords - lo) / (hi - lo + 1e-9)


# ---------------------------------------------------------------------------
# Run one config
# ---------------------------------------------------------------------------

def run_config(X, n_neighbors, min_dist, metric, unit_8, sample_idx, gt_nbrs, genre_sub):
    t0 = time.time()
    reducer = umap.UMAP(
        n_components=3,
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric=metric,
        n_epochs=200,
        random_state=RANDOM_STATE,
        verbose=False,
    )
    coords  = normalize_coords(reducer.fit_transform(X).astype(np.float32))
    elapsed = time.time() - t0

    coords_sub = coords[sample_idx]
    unit_sub   = unit_8[sample_idx]

    trust  = trustworthiness(unit_sub, coords_sub, n_neighbors=K_NEIGHBORS, metric="cosine")
    recall = knn_recall(coords_sub, gt_nbrs, K_NEIGHBORS)
    sil    = silhouette_score(coords_sub, genre_sub, metric="euclidean",
                              sample_size=1000, random_state=RANDOM_STATE)

    return {
        "metric":          metric,
        "n_neighbors":     n_neighbors,
        "min_dist":        min_dist,
        "trustworthiness": round(trust,  4),
        "knn_recall":      round(recall, 4),
        "silhouette":      round(sil,    4),
        "combined":        round((trust + recall) / 2, 4),
        "time_s":          round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Heatmap helper
# ---------------------------------------------------------------------------

def _make_heatmap(ax, df_metric, value_col, title, cmap, fmt=".3f"):
    pivot = df_metric.pivot(index="n_neighbors", columns="min_dist", values=value_col)
    sns.heatmap(
        pivot, ax=ax, annot=True, fmt=fmt, cmap=cmap,
        linewidths=0.4, linecolor="white",
        cbar_kws={"shrink": 0.8},
        annot_kws={"size": 8},
    )
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("min_dist", fontsize=9)
    ax.set_ylabel("n_neighbors", fontsize=9)


def plot_heatmaps(df):
    metrics = df["metric"].unique()
    n_m = len(metrics)

    for value_col, label, cmap, fname in [
        ("trustworthiness", "Trustworthiness",      "Blues",  "heatmap_trust.png"),
        ("knn_recall",      "k-NN Recall @10",      "Reds",   "heatmap_recall.png"),
        ("combined",        "Avg(Trust + Recall)/2", "Greens", "heatmap_combined.png"),
    ]:
        fig, axes = plt.subplots(1, n_m, figsize=(6 * n_m, 5))
        fig.suptitle(
            f"UMAP Sweep — {label}\nFeature set: 8 audio + genre×{GENRE_WEIGHT}  |  "
            f"ground-truth: cosine k-NN on audio unit vectors",
            fontsize=11,
        )
        for ax, m in zip(axes, metrics):
            _make_heatmap(ax, df[df["metric"] == m], value_col, f"metric={m}", cmap)

        fig.tight_layout()
        out = FIG_DIR / fname
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    X, unit_8, meta = load_data()

    rng        = np.random.default_rng(RANDOM_STATE)
    sample_idx = rng.choice(len(X), size=min(SAMPLE_N, len(X)), replace=False)
    genre_enc  = LabelEncoder().fit_transform(meta["playlist_genre"])
    genre_sub  = genre_enc[sample_idx]

    print(f"\nComputing ground-truth cosine k-NN (k={K_NEIGHBORS}) on {len(sample_idx)} subsample ...")
    gt_nbrs = compute_gt_neighbors(unit_8, sample_idx, K_NEIGHBORS)

    configs = list(itertools.product(METRIC_GRID, N_NEIGHBORS_GRID, MIN_DIST_GRID))
    print(f"\nRunning {len(configs)} configs ...\n")

    results = []
    for i, (metric, n_neighbors, min_dist) in enumerate(configs, 1):
        tag = f"[{i:02d}/{len(configs)}] metric={metric:<12} n_neighbors={n_neighbors:<3} min_dist={min_dist}"
        print(tag, end="  ", flush=True)
        r = run_config(X, n_neighbors, min_dist, metric, unit_8, sample_idx, gt_nbrs, genre_sub)
        print(f"trust={r['trustworthiness']}  recall={r['knn_recall']}  sil={r['silhouette']}  ({r['time_s']}s)")
        results.append(r)

    df = pd.DataFrame(results)
    out_csv = RESULTS_DIR / "05_sweep.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {out_csv}")

    # Winner
    winner = df.loc[df["combined"].idxmax()]
    print("\n--- Top 5 configs (avg trust + recall) ---")
    top5 = df.nlargest(5, "combined")[["metric", "n_neighbors", "min_dist",
                                        "trustworthiness", "knn_recall", "silhouette", "combined"]]
    print(top5.to_string(index=False))

    print(f"\nWinner: metric={winner['metric']}  n_neighbors={int(winner['n_neighbors'])}  "
          f"min_dist={winner['min_dist']}")
    print(f"  trustworthiness={winner['trustworthiness']}  "
          f"knn_recall={winner['knn_recall']}  silhouette={winner['silhouette']}")

    print("\nGenerating heatmaps ...")
    plot_heatmaps(df)

    print("\nDone. Record winner config in 06_summary.md.")


if __name__ == "__main__":
    main()
