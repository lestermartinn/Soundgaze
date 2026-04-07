"""
Dimensionality Reduction Comparison
=============================================
Compares PCA, UMAP, t-SNE, and PaCMAP for reducing the 8-feature audio space to 3D.

Input:
  features_minmax.npz  -- 8-feature MinMax-scaled matrix (same input for all methods)
  features_unit.npz    -- L2-normalized unit vectors (used only for ground-truth k-NN)
  metadata.csv         -- genre + track info for plot coloring

Metrics (computed on a subsample for speed; all use the same subsample):
  Trustworthiness      -- are 3D neighbors also cosine neighbors in 8D? (sklearn)
  k-NN recall @ k=10   -- fraction of true top-10 cosine neighbors recovered in 3D
  Silhouette score     -- genre cluster separation in 3D (higher = tighter genre clusters)

Outputs:
  figures/03_reduction/{pca,umap,tsne,pacmap}_scatter.png  -- 4-panel scatter per method
  figures/03_reduction/metrics_comparison.png               -- side-by-side bar chart
  results/03_metrics.csv                                    -- numeric results table

Note on t-SNE: sklearn t-SNE has no transform() for new points. If t-SNE wins,
real-time user track projection in the backend would break. See PLAN.md.

Run from analysis/:
  python 03_reduction_comparison.py
"""

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE, trustworthiness
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import LabelEncoder
import pacmap
import umap

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANALYSIS_DIR = Path(__file__).parent.parent.parent
DATA_DIR     = ANALYSIS_DIR / "data"
FIG_DIR      = ANALYSIS_DIR / "figures" / "03_reduction"
RESULTS_DIR  = ANALYSIS_DIR / "results"

SAMPLE_N     = 3000   # subsample size for O(n²) metrics (trustworthiness, silhouette)
K_NEIGHBORS  = 10     # k for k-NN recall
RANDOM_STATE = 42

FEATURE_COLS = [
    "danceability", "energy", "loudness", "speechiness",
    "instrumentalness", "liveness", "valence", "tempo",
]

# Features to color scatter plots by (besides genre)
AUDIO_COLOR_COLS = ["energy", "valence", "danceability"]

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_data() -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """
    Returns
    -------
    minmax : (N, 8) MinMax-scaled — input to all reducers
    unit   : (N, 8) L2-normalized — used only for cosine ground-truth k-NN
    meta   : DataFrame with track_id, playlist_genre, and audio features for coloring
    """
    for p in [DATA_DIR / "features_minmax.npz", DATA_DIR / "features_unit.npz", DATA_DIR / "metadata.csv"]:
        if not p.exists():
            print(f"ERROR: {p} not found -- run 01_ingest.py first.", file=sys.stderr)
            sys.exit(1)

    minmax = np.load(DATA_DIR / "features_minmax.npz", allow_pickle=True)["features"]
    unit   = np.load(DATA_DIR / "features_unit.npz",   allow_pickle=True)["features"]
    meta   = pd.read_csv(DATA_DIR / "metadata.csv")

    # Also load raw features for coloring plots (energy, valence, danceability)
    raw_npz = np.load(DATA_DIR / "features_raw.npz", allow_pickle=True)
    raw_arr = raw_npz["features"]
    raw_cols = raw_npz["cols"].tolist()
    for col in AUDIO_COLOR_COLS:
        if col in raw_cols:
            meta[col] = raw_arr[:, raw_cols.index(col)]

    print(f"Loaded {len(minmax)} tracks, {minmax.shape[1]} features")
    return minmax, unit, meta


# ---------------------------------------------------------------------------
# Ground-truth k-NN (cosine on unit vectors)
# ---------------------------------------------------------------------------

def compute_gt_neighbors(unit: np.ndarray, idx: np.ndarray, k: int) -> np.ndarray:
    """
    Returns (len(idx), k) array of ground-truth cosine neighbor indices
    within the subsample (indices are local to idx, not global).
    """
    X = unit[idx]
    nn = NearestNeighbors(n_neighbors=k + 1, metric="cosine", n_jobs=-1).fit(X)
    _, nbrs = nn.kneighbors(X)
    return nbrs[:, 1:]   # exclude self


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def knn_recall(coords_3d_sub: np.ndarray, gt_nbrs: np.ndarray, k: int) -> float:
    """
    Fraction of ground-truth cosine top-k neighbors recovered in 3D euclidean top-k.
    coords_3d_sub and gt_nbrs must be indexed the same (subsample-local indices).
    """
    nn_3d = NearestNeighbors(n_neighbors=k + 1, metric="euclidean", n_jobs=-1).fit(coords_3d_sub)
    _, nbrs_3d = nn_3d.kneighbors(coords_3d_sub)
    nbrs_3d = nbrs_3d[:, 1:]   # exclude self

    recall = np.mean([
        len(set(gt_nbrs[i]) & set(nbrs_3d[i])) / k
        for i in range(len(gt_nbrs))
    ])
    return float(recall)


def compute_metrics(
    unit_sub: np.ndarray,
    coords_3d_sub: np.ndarray,
    gt_nbrs: np.ndarray,
    genre_labels_sub: np.ndarray,
) -> dict:
    trust = trustworthiness(unit_sub, coords_3d_sub, n_neighbors=K_NEIGHBORS, metric="cosine")
    recall = knn_recall(coords_3d_sub, gt_nbrs, K_NEIGHBORS)
    sil = silhouette_score(coords_3d_sub, genre_labels_sub, metric="euclidean", sample_size=1000, random_state=RANDOM_STATE)
    return {"trustworthiness": round(trust, 4), "knn_recall": round(recall, 4), "silhouette": round(sil, 4)}


# ---------------------------------------------------------------------------
# Scatter plots
# ---------------------------------------------------------------------------

GENRE_PALETTE = {
    "edm":   "#1DB954",
    "latin": "#FF6B35",
    "pop":   "#E91E8C",
    "r&b":   "#9B59B6",
    "rap":   "#F1C40F",
    "rock":  "#3498DB",
}

def _genre_colors(genres: pd.Series) -> list:
    return [GENRE_PALETTE.get(g, "#AAAAAA") for g in genres]


def plot_scatter(name: str, coords: np.ndarray, meta: pd.DataFrame) -> None:
    """
    4-panel scatter: XY projection colored by genre, energy, valence, danceability.
    Uses a random subsample of 5000 points for plot clarity.
    """
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RANDOM_STATE)
    plot_idx = rng.choice(len(coords), size=min(5000, len(coords)), replace=False)
    c = coords[plot_idx]
    m = meta.iloc[plot_idx].reset_index(drop=True)

    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    fig.suptitle(f"{name.upper()} — 3D layout (XY projection, {len(plot_idx):,} songs)", fontsize=13)

    # Panel 1: genre
    ax = axes[0]
    for genre, color in GENRE_PALETTE.items():
        mask = m["playlist_genre"] == genre
        ax.scatter(c[mask, 0], c[mask, 1], c=color, s=2, alpha=0.5, label=genre, rasterized=True)
    ax.set_title("Genre")
    ax.legend(markerscale=4, fontsize=7, loc="upper right")
    ax.set_xlabel("dim 1"); ax.set_ylabel("dim 2")

    # Panels 2-4: audio features
    for ax, col in zip(axes[1:], AUDIO_COLOR_COLS):
        if col in m.columns:
            sc = ax.scatter(c[:, 0], c[:, 1], c=m[col], cmap="plasma", s=2, alpha=0.5, rasterized=True)
            plt.colorbar(sc, ax=ax, shrink=0.8)
        ax.set_title(col.capitalize())
        ax.set_xlabel("dim 1"); ax.set_ylabel("dim 2")

    fig.tight_layout()
    out = FIG_DIR / f"{name.lower()}_scatter.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


# ---------------------------------------------------------------------------
# Metrics bar chart
# ---------------------------------------------------------------------------

def plot_metrics(results: list[dict]) -> None:
    df = pd.DataFrame(results).set_index("method")
    metrics = ["trustworthiness", "knn_recall", "silhouette"]
    labels  = ["Trustworthiness", "k-NN Recall @10", "Silhouette (genre)"]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    fig.suptitle("Reduction Method Comparison (8-feature minmax input, cosine ground truth)", fontsize=12)

    colors = ["#3498DB", "#E91E8C", "#1DB954", "#F39C12"]
    for ax, metric, label in zip(axes, metrics, labels):
        vals = df[metric]
        bars = ax.bar(vals.index, vals.values, color=colors, edgecolor="white", linewidth=0.5)
        ax.set_title(label, fontsize=11)
        ax.set_ylim(0, min(1.05, vals.max() * 1.2))
        ax.set_ylabel("Score")
        for bar, val in zip(bars, vals.values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=9)

    fig.tight_layout()
    out = FIG_DIR / "metrics_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


# ---------------------------------------------------------------------------
# Reduction runners
# ---------------------------------------------------------------------------

def run_pca(minmax: np.ndarray) -> np.ndarray:
    print("  Fitting PCA ...")
    pca = PCA(n_components=3, random_state=RANDOM_STATE)
    coords = pca.fit_transform(minmax).astype(np.float32)
    evr = pca.explained_variance_ratio_
    print(f"  Explained variance: PC1={evr[0]:.3f}  PC2={evr[1]:.3f}  PC3={evr[2]:.3f}  total={evr.sum():.3f}")
    return coords


def run_umap(minmax: np.ndarray) -> np.ndarray:
    print("  Fitting UMAP (cosine, n_neighbors=40, min_dist=0.4) ...")
    reducer = umap.UMAP(
        n_components=3,
        metric="cosine",
        n_neighbors=40,
        min_dist=0.4,
        n_epochs=200,
        random_state=RANDOM_STATE,
        verbose=False,
    )
    return reducer.fit_transform(minmax).astype(np.float32)


def run_tsne(minmax: np.ndarray) -> np.ndarray:
    print("  Fitting t-SNE (cosine, perplexity=30) — this may take several minutes ...")
    tsne = TSNE(
        n_components=3,
        perplexity=30,
        metric="cosine",
        max_iter=500,
        random_state=RANDOM_STATE,
        verbose=1,
    )
    return tsne.fit_transform(minmax).astype(np.float32)


def run_pacmap(minmax: np.ndarray) -> np.ndarray:
    print("  Fitting PaCMAP (n_neighbors=10, MN_ratio=0.5, FP_ratio=2.0) ...")
    reducer = pacmap.PaCMAP(
        n_components=3,
        n_neighbors=10,
        MN_ratio=0.5,
        FP_ratio=2.0,
        random_state=RANDOM_STATE,
        verbose=False,
    )
    return reducer.fit_transform(minmax).astype(np.float32)


# ---------------------------------------------------------------------------
# Normalize 3D coords to [0, 1] per axis for fair metric comparison
# ---------------------------------------------------------------------------

def normalize_coords(coords: np.ndarray) -> np.ndarray:
    lo = coords.min(axis=0)
    hi = coords.max(axis=0)
    return (coords - lo) / (hi - lo + 1e-9)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    minmax, unit, meta = load_data()

    # Fixed subsample for all metric computations
    rng = np.random.default_rng(RANDOM_STATE)
    sample_idx = rng.choice(len(minmax), size=min(SAMPLE_N, len(minmax)), replace=False)
    unit_sub   = unit[sample_idx]
    genre_enc  = LabelEncoder().fit_transform(meta["playlist_genre"])
    genre_sub  = genre_enc[sample_idx]

    print(f"\nComputing ground-truth cosine k-NN (k={K_NEIGHBORS}) on {len(sample_idx)} subsample ...")
    gt_nbrs = compute_gt_neighbors(unit, sample_idx, K_NEIGHBORS)

    methods = [
        ("PCA",    run_pca),
        ("UMAP",   run_umap),
        ("tSNE",   run_tsne),
        ("PaCMAP", run_pacmap),
    ]

    results = []
    for name, runner in methods:
        print(f"\n{'='*50}")
        print(f"[{name}]")
        t0 = time.time()
        coords = runner(minmax)
        coords = normalize_coords(coords)
        elapsed = time.time() - t0
        print(f"  Done in {elapsed:.1f}s")

        print("  Computing metrics ...")
        coords_sub = coords[sample_idx]
        m = compute_metrics(unit_sub, coords_sub, gt_nbrs, genre_sub)
        m["method"] = name
        m["time_s"] = round(elapsed, 1)
        results.append(m)
        print(f"  trustworthiness={m['trustworthiness']}  knn_recall={m['knn_recall']}  silhouette={m['silhouette']}")

        print("  Generating scatter plot ...")
        plot_scatter(name, coords, meta)

    print(f"\n{'='*50}")
    print("\nGenerating metrics comparison chart ...")
    plot_metrics(results)

    df = pd.DataFrame(results)[["method", "trustworthiness", "knn_recall", "silhouette", "time_s"]]
    out_csv = RESULTS_DIR / "03_metrics.csv"
    df.to_csv(out_csv, index=False)
    print(f"Saved {out_csv}")

    print("\n--- Results ---")
    print(df.to_string(index=False))

    winner = df.loc[df[["trustworthiness", "knn_recall"]].mean(axis=1).idxmax(), "method"]
    print(f"\nLeading method (avg trustworthiness + k-NN recall): {winner}")
    print("Review t-SNE transform() limitation in PLAN.md before selecting it as winner.")
    print("\nDone. Run 04_feature_ablation.py next with the winning method.")


if __name__ == "__main__":
    main()
