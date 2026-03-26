"""
TriMAP Evaluation
=============================================
Tests TriMAP as a drop-in replacement for UMAP on the final feature set.
TriMAP optimises a triplet ranking objective (anchor closer to near neighbors
than far ones), which targets k-NN recall more directly than UMAP's fuzzy
topological loss.

Both methods receive the same input and are evaluated on the same subsample
with the same ground-truth k-NN to ensure a controlled comparison.

Decision gate: if TriMAP recall >= UMAP recall + 0.02, adopt it in the backend.

Feature set : 8 audio features + genre one-hot x 0.1
UMAP config : cosine, n_neighbors=40, min_dist=0.25  (Phase 5 winner)
TriMAP config: cosine, n_inliers=12, n_outliers=4, n_random=3

Input
-----
  data/features_minmax.npz
  data/features_unit.npz
  data/genres_onehot.npz
  data/metadata.csv

Output
------
  results/07_trimap.csv
  figures/07_trimap/scatter_comparison.png  -- side-by-side genre scatter
  figures/07_trimap/metrics_comparison.png  -- bar chart trust / recall / sil

Run from analysis/:
  python 07_trimap_eval.py
"""

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import trimap
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
FIG_DIR      = ANALYSIS_DIR / "figures" / "07_trimap"
RESULTS_DIR  = ANALYSIS_DIR / "results"

GENRE_WEIGHT = 0.1
SAMPLE_N     = 3000
K_NEIGHBORS  = 10
RANDOM_STATE = 42

UMAP_KWARGS = dict(
    n_components=3,
    metric="cosine",
    n_neighbors=40,
    min_dist=0.25,
    n_epochs=200,
    random_state=RANDOM_STATE,
    verbose=False,
)

TRIMAP_KWARGS = dict(
    n_dims=3,
    distance="cosine",
    n_inliers=12,
    n_outliers=4,
    n_random=3,
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

    X = np.concatenate([minmax_8, genre_onehot * GENRE_WEIGHT], axis=1)
    print(f"Loaded {len(X)} tracks  |  input shape: {X.shape}")
    return X, unit_8, meta


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_gt_neighbors(unit, idx, k):
    nn = NearestNeighbors(n_neighbors=k + 1, metric="cosine", n_jobs=-1).fit(unit[idx])
    _, nbrs = nn.kneighbors(unit[idx])
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


def compute_metrics(unit_sub, coords_sub, gt_nbrs, genre_sub):
    trust  = trustworthiness(unit_sub, coords_sub, n_neighbors=K_NEIGHBORS, metric="cosine")
    recall = knn_recall(coords_sub, gt_nbrs, K_NEIGHBORS)
    sil    = silhouette_score(coords_sub, genre_sub, metric="euclidean",
                              sample_size=1000, random_state=RANDOM_STATE)
    return round(trust, 4), round(recall, 4), round(sil, 4)


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_scatter_comparison(coords_umap, coords_trimap, meta):
    rng      = np.random.default_rng(RANDOM_STATE)
    plot_idx = rng.choice(len(meta), size=min(5000, len(meta)), replace=False)
    genres   = meta["playlist_genre"].iloc[plot_idx].reset_index(drop=True)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(
        f"UMAP vs TriMAP — XY Projection (5k songs)\n"
        f"Feature set: 8 audio + genre×{GENRE_WEIGHT}",
        fontsize=12,
    )
    for ax, coords, title in [
        (axes[0], coords_umap,   "UMAP  (cosine, n=40, d=0.25)"),
        (axes[1], coords_trimap, "TriMAP  (cosine, inliers=12, outliers=4)"),
    ]:
        c = coords[plot_idx]
        for genre, color in GENRE_PALETTE.items():
            mask = genres == genre
            ax.scatter(c[mask, 0], c[mask, 1], c=color, s=1.5, alpha=0.5,
                       label=genre, rasterized=True)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("dim 1", fontsize=9)
        ax.set_ylabel("dim 2", fontsize=9)

    axes[0].legend(markerscale=5, fontsize=8, loc="upper right")
    fig.tight_layout()
    out = FIG_DIR / "scatter_comparison.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


def plot_metrics_comparison(rows):
    methods = [r["method"] for r in rows]
    x = np.arange(len(methods))
    width = 0.25

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.suptitle("UMAP vs TriMAP — Metric Comparison", fontsize=12)

    for i, (col, label, color) in enumerate([
        ("trustworthiness", "Trustworthiness", "#3498DB"),
        ("knn_recall",      "k-NN Recall @10", "#E91E8C"),
        ("silhouette",      "Silhouette",       "#1DB954"),
    ]):
        bars = ax.bar(x + i * width, [r[col] for r in rows], width,
                      label=label, color=color, edgecolor="white")
        for bar, r in zip(bars, rows):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                    f"{r[col]:.3f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x + width)
    ax.set_xticklabels(methods, fontsize=10)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Score")
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = FIG_DIR / "metrics_comparison.png"
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

    results = []

    # ---- UMAP (Phase 5 winner) ----
    print("\n[1/2] Fitting UMAP (cosine, n_neighbors=40, min_dist=0.25) ...")
    t0 = time.time()
    coords_umap = normalize_coords(
        umap.UMAP(**UMAP_KWARGS).fit_transform(X).astype(np.float32)
    )
    umap_time = time.time() - t0
    trust, recall, sil = compute_metrics(unit_8[sample_idx], coords_umap[sample_idx], gt_nbrs, genre_sub)
    print(f"  trust={trust}  recall={recall}  sil={sil}  ({umap_time:.1f}s)")
    results.append({"method": "UMAP", "trustworthiness": trust,
                    "knn_recall": recall, "silhouette": sil, "time_s": round(umap_time, 1)})

    # ---- TriMAP ----
    print("\n[2/2] Fitting TriMAP (cosine, n_inliers=12, n_outliers=4, n_random=3) ...")
    t0 = time.time()
    coords_trimap = normalize_coords(
        trimap.TRIMAP(**TRIMAP_KWARGS).fit_transform(X).astype(np.float32)
    )
    trimap_time = time.time() - t0
    trust, recall, sil = compute_metrics(unit_8[sample_idx], coords_trimap[sample_idx], gt_nbrs, genre_sub)
    print(f"  trust={trust}  recall={recall}  sil={sil}  ({trimap_time:.1f}s)")
    results.append({"method": "TriMAP", "trustworthiness": trust,
                    "knn_recall": recall, "silhouette": sil, "time_s": round(trimap_time, 1)})

    # ---- Save ----
    df = pd.DataFrame(results)
    out_csv = RESULTS_DIR / "07_trimap.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {out_csv}")

    print("\n--- Results ---")
    print(df.to_string(index=False))

    # ---- Decision ----
    umap_recall   = df.loc[df["method"] == "UMAP",   "knn_recall"].values[0]
    trimap_recall = df.loc[df["method"] == "TriMAP", "knn_recall"].values[0]
    delta = trimap_recall - umap_recall
    print(f"\nΔ recall (TriMAP − UMAP): {delta:+.4f}  (threshold: +0.02)")
    if delta >= 0.02:
        print("  ADOPT TriMAP — recall improvement meets threshold.")
    elif delta >= 0:
        print("  MARGINAL — TriMAP matches UMAP but doesn't clear +0.02 threshold. Keep UMAP.")
    else:
        print("  KEEP UMAP — TriMAP does not improve recall.")

    # ---- Plots ----
    print("\nGenerating plots ...")
    plot_scatter_comparison(coords_umap, coords_trimap, meta)
    plot_metrics_comparison(results)

    print("\nDone.")


if __name__ == "__main__":
    main()
