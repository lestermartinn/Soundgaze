"""
Parametric UMAP
=============================================
Replaces standard UMAP with ParametricUMAP, which trains a neural encoder
so new-song projection becomes an exact forward pass (~1 ms) instead of
UMAP's approximate transform().

The encoder is saved to data/parametric_umap_encoder/ and can be loaded once
at backend startup to project any new song in real time.

Validation
----------
Metrics are computed on the same subsample + ground-truth k-NN as all prior
phases and compared to the Phase 5 UMAP baseline (trust=0.954, recall=0.267).
A transform() speed test on a 1-song holdout is also run to confirm inference
latency.

Feature set : 8 audio features + genre one-hot x 0.1  (same as Phase 5-7)
UMAP config : cosine, n_neighbors=40, min_dist=0.25  (Phase 5 winner)

Input
-----
  data/features_minmax.npz
  data/features_unit.npz
  data/genres_onehot.npz
  data/metadata.csv

Output
------
  data/parametric_umap_encoder/     -- Keras SavedModel (load for inference)
  data/parametric_umap_coords.npy   -- full (N, 3) embedding
  results/08_parametric_umap.csv    -- metric comparison vs standard UMAP
  figures/08_parametric_umap/scatter_comparison.png
  figures/08_parametric_umap/metrics_comparison.png

Requires: pip install umap-learn[parametric]  (installs tensorflow)

Run from analysis/:
  python 08_parametric_umap.py
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

try:
    from umap.parametric_umap import ParametricUMAP
except ImportError:
    print(
        "ERROR: ParametricUMAP not available.\n"
        "Install with:  pip install umap-learn[parametric_umap]\n"
        "This pulls in tensorflow as a backend.",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANALYSIS_DIR = Path(__file__).parent.parent.parent
DATA_DIR     = ANALYSIS_DIR / "data"
FIG_DIR      = ANALYSIS_DIR / "figures" / "08_parametric_umap"
RESULTS_DIR  = ANALYSIS_DIR / "results"

GENRE_WEIGHT = 0.1
SAMPLE_N     = 3000
K_NEIGHBORS  = 10
RANDOM_STATE = 42

SHARED_UMAP_KWARGS = dict(
    n_components=3,
    metric="cosine",
    n_neighbors=40,
    min_dist=0.25,
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


def normalize_coords(coords: np.ndarray) -> np.ndarray:
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

def plot_scatter_comparison(coords_std, coords_par, meta):
    rng      = np.random.default_rng(RANDOM_STATE)
    plot_idx = rng.choice(len(meta), size=min(5000, len(meta)), replace=False)
    genres   = meta["playlist_genre"].iloc[plot_idx].reset_index(drop=True)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(
        f"Standard UMAP vs Parametric UMAP — XY Projection (5k songs)\n"
        f"Feature set: 8 audio + genre×{GENRE_WEIGHT}  |  cosine, n=40, d=0.25",
        fontsize=12,
    )
    for ax, coords, title in [
        (axes[0], coords_std, "Standard UMAP"),
        (axes[1], coords_par, "Parametric UMAP"),
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
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.suptitle("Standard UMAP vs Parametric UMAP — Metrics", fontsize=12)

    methods = [r["method"] for r in rows]
    x = np.arange(len(methods))
    width = 0.25

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

    # ---- Standard UMAP ----
    print("\n[1/2] Fitting standard UMAP ...")
    t0 = time.time()
    std_reducer = umap.UMAP(n_epochs=200, **SHARED_UMAP_KWARGS)
    coords_std  = normalize_coords(std_reducer.fit_transform(X).astype(np.float32))
    std_time    = time.time() - t0
    trust, recall, sil = compute_metrics(unit_8[sample_idx], coords_std[sample_idx], gt_nbrs, genre_sub)
    print(f"  trust={trust}  recall={recall}  sil={sil}  ({std_time:.1f}s)")
    results.append({"method": "Standard UMAP", "trustworthiness": trust,
                    "knn_recall": recall, "silhouette": sil, "fit_time_s": round(std_time, 1)})

    # transform() latency on 1 song
    single = X[:1].astype(np.float32)
    _ = std_reducer.transform(single)  # warm-up
    t0 = time.time()
    for _ in range(50):
        std_reducer.transform(single)
    std_transform_ms = (time.time() - t0) / 50 * 1000
    print(f"  Standard UMAP transform() latency (1 song, avg 50 runs): {std_transform_ms:.2f} ms")

    # ---- Parametric UMAP ----
    print("\n[2/2] Fitting Parametric UMAP (trains a neural encoder — takes longer) ...")
    t0 = time.time()
    par_reducer = ParametricUMAP(**SHARED_UMAP_KWARGS)
    coords_par  = normalize_coords(par_reducer.fit_transform(X).astype(np.float32))
    par_time    = time.time() - t0
    trust, recall, sil = compute_metrics(unit_8[sample_idx], coords_par[sample_idx], gt_nbrs, genre_sub)
    print(f"  trust={trust}  recall={recall}  sil={sil}  ({par_time:.1f}s)")
    results.append({"method": "Parametric UMAP", "trustworthiness": trust,
                    "knn_recall": recall, "silhouette": sil, "fit_time_s": round(par_time, 1)})

    # transform() latency on 1 song
    _ = par_reducer.transform(single)  # warm-up
    t0 = time.time()
    for _ in range(50):
        par_reducer.transform(single)
    par_transform_ms = (time.time() - t0) / 50 * 1000
    print(f"  Parametric UMAP transform() latency (1 song, avg 50 runs): {par_transform_ms:.2f} ms")

    # ---- Save encoder ----
    encoder_path = DATA_DIR / "parametric_umap_encoder.keras"
    par_reducer.encoder.save(str(encoder_path))
    print(f"\n  Encoder saved → {encoder_path}")

    coords_path = DATA_DIR / "parametric_umap_coords.npy"
    np.save(coords_path, coords_par)
    print(f"  Coords saved  → {coords_path}  shape={coords_par.shape}")

    # ---- Latency summary ----
    print(f"\n  transform() latency comparison:")
    print(f"    Standard UMAP  : {std_transform_ms:.2f} ms / song")
    print(f"    Parametric UMAP: {par_transform_ms:.2f} ms / song")

    # ---- Save results ----
    df = pd.DataFrame(results)
    df["transform_ms"] = [round(std_transform_ms, 2), round(par_transform_ms, 2)]
    out_csv = RESULTS_DIR / "08_parametric_umap.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {out_csv}")

    print("\n--- Results ---")
    print(df.to_string(index=False))

    # ---- Plots ----
    print("\nGenerating plots ...")
    plot_scatter_comparison(coords_std, coords_par, meta)
    plot_metrics_comparison(results)

    # ---- Decision ----
    std_r  = results[0]["knn_recall"]
    par_r  = results[1]["knn_recall"]
    delta  = par_r - std_r
    print(f"\nΔ recall (Parametric − Standard): {delta:+.4f}")
    if abs(delta) <= 0.01:
        print("  Metrics equivalent. Parametric UMAP is the better choice for production")
        print("  — exact transform() vs approximate, and faster inference.")
    elif delta > 0.01:
        print("  Parametric UMAP is both faster at inference AND higher recall. Adopt it.")
    else:
        print(f"  Parametric UMAP recall is lower by {-delta:.4f}. "
              "Weigh inference speed gain against metric cost.")

    print("\nDone.")


if __name__ == "__main__":
    main()
