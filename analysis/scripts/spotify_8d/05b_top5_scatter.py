"""
Top-5 Config Point Cloud Scatter
=============================================
Reads 05_sweep.csv, re-fits UMAP for the top 5 configs (by avg trust + recall),
and plots a scatter grid: one panel per config, colored by genre.
Also generates XY / XZ / YZ projections for the overall winner.

Run from analysis/:
  python 05b_top5_scatter.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import umap
from sklearn.preprocessing import LabelEncoder

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANALYSIS_DIR = Path(__file__).parent.parent.parent
DATA_DIR     = ANALYSIS_DIR / "data"
FIG_DIR      = ANALYSIS_DIR / "figures" / "05_sweep"
RESULTS_DIR  = ANALYSIS_DIR / "results"

GENRE_WEIGHT = 0.1
RANDOM_STATE = 42
TOP_N        = 5

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
    for p in [DATA_DIR / "features_minmax.npz", DATA_DIR / "genres_onehot.npz",
              DATA_DIR / "metadata.csv", RESULTS_DIR / "05_sweep.csv"]:
        if not p.exists():
            print(f"ERROR: {p} not found.", file=sys.stderr)
            sys.exit(1)

    minmax_8     = np.load(DATA_DIR / "features_minmax.npz", allow_pickle=True)["features"]
    genre_npz    = np.load(DATA_DIR / "genres_onehot.npz",   allow_pickle=True)
    genre_onehot = genre_npz["features"]
    meta         = pd.read_csv(DATA_DIR / "metadata.csv")
    sweep_df     = pd.read_csv(RESULTS_DIR / "05_sweep.csv")

    X = np.concatenate([minmax_8, genre_onehot * GENRE_WEIGHT], axis=1)
    return X, meta, sweep_df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_coords(coords):
    lo = coords.min(axis=0)
    hi = coords.max(axis=0)
    return (coords - lo) / (hi - lo + 1e-9)


def fit_umap(X, metric, n_neighbors, min_dist):
    reducer = umap.UMAP(
        n_components=3,
        metric=metric,
        n_neighbors=int(n_neighbors),
        min_dist=float(min_dist),
        n_epochs=200,
        random_state=RANDOM_STATE,
        verbose=False,
    )
    return normalize_coords(reducer.fit_transform(X).astype(np.float32))


def genre_scatter(ax, coords, meta, proj=(0, 1), show_legend=False):
    rng      = np.random.default_rng(RANDOM_STATE)
    idx      = rng.choice(len(coords), size=min(5000, len(coords)), replace=False)
    c        = coords[idx]
    genres   = meta["playlist_genre"].iloc[idx].reset_index(drop=True)
    a, b     = proj
    for genre, color in GENRE_PALETTE.items():
        mask = genres == genre
        ax.scatter(c[mask, a], c[mask, b], c=color, s=1.5, alpha=0.5,
                   label=genre, rasterized=True)
    if show_legend:
        ax.legend(markerscale=5, fontsize=7, loc="upper right")
    ax.tick_params(labelsize=7)


# ---------------------------------------------------------------------------
# Plot: top-5 comparison grid (XY projection)
# ---------------------------------------------------------------------------

def plot_top5_grid(top5_rows, all_coords, meta):
    fig, axes = plt.subplots(1, TOP_N, figsize=(5 * TOP_N, 5))
    fig.suptitle(
        f"Top {TOP_N} UMAP Configs — XY Projection (5k songs, colored by genre)\n"
        f"Feature set: 8 audio + genre×{GENRE_WEIGHT}",
        fontsize=12,
    )
    for ax, (_, row), coords in zip(axes, top5_rows.iterrows(), all_coords):
        genre_scatter(ax, coords, meta, proj=(0, 1), show_legend=(ax == axes[0]))
        ax.set_title(
            f"metric={row['metric']}\nn={int(row['n_neighbors'])}  d={row['min_dist']}\n"
            f"trust={row['trustworthiness']}  recall={row['knn_recall']}",
            fontsize=8,
        )
        ax.set_xlabel("dim 1", fontsize=8)
        ax.set_ylabel("dim 2", fontsize=8)

    fig.tight_layout()
    out = FIG_DIR / "top5_scatter.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


# ---------------------------------------------------------------------------
# Plot: winner — XY / XZ / YZ projections
# ---------------------------------------------------------------------------

def plot_winner_projections(row, coords, meta):
    proj_labels = [("dim 1", "dim 2"), ("dim 1", "dim 3"), ("dim 2", "dim 3")]
    projections = [(0, 1), (0, 2), (1, 2)]

    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    fig.suptitle(
        f"Winner Config — All 3 Projections\n"
        f"metric={row['metric']}  n_neighbors={int(row['n_neighbors'])}  "
        f"min_dist={row['min_dist']}  |  "
        f"trust={row['trustworthiness']}  recall={row['knn_recall']}  sil={row['silhouette']}",
        fontsize=11,
    )
    for ax, (xl, yl), proj in zip(axes, proj_labels, projections):
        genre_scatter(ax, coords, meta, proj=proj, show_legend=(ax == axes[0]))
        ax.set_xlabel(xl, fontsize=9)
        ax.set_ylabel(yl, fontsize=9)

    fig.tight_layout()
    out = FIG_DIR / "winner_projections.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    X, meta, sweep_df = load_data()
    top5 = sweep_df.nlargest(TOP_N, "combined").reset_index(drop=True)

    print(f"Top {TOP_N} configs:")
    print(top5[["metric", "n_neighbors", "min_dist",
                "trustworthiness", "knn_recall", "silhouette", "combined"]].to_string(index=False))
    print(f"\nFitting {TOP_N} UMAP models ...\n")

    all_coords = []
    for i, row in top5.iterrows():
        print(f"  [{i+1}/{TOP_N}] metric={row['metric']}  n_neighbors={int(row['n_neighbors'])}  min_dist={row['min_dist']}")
        coords = fit_umap(X, row["metric"], row["n_neighbors"], row["min_dist"])
        all_coords.append(coords)

    print("\nGenerating plots ...")
    plot_top5_grid(top5, all_coords, meta)
    plot_winner_projections(top5.iloc[0], all_coords[0], meta)

    print("\nDone.")


if __name__ == "__main__":
    main()
