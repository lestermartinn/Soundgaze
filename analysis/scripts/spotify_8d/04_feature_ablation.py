"""
Feature Set Ablation
=============================================
Tests which audio features are essential for the 3D sonic layout, and whether
adding one-hot genre columns (weighted at GENRE_WEIGHT) consistently helps.

All experiments use UMAP (winner from 03_reduction_comparison.py).
Ground-truth k-NN is always cosine on the original 8-feature L2-normalised
vectors, so every metric measures how well audio similarity is preserved.

Experiments
-----------
  Baseline         : 8 audio features  (audio-only and +genre)
  Leave-one-out    : drop one audio feature at a time (audio-only)
  add_acousticness : append acousticness to baseline (audio-only)
  swap_loudness    : replace loudness with acousticness (audio-only)
  Best subset      : best audio-only feature set found above (+genre re-test)

Input
-----
  data/features_minmax.npz        -- 8-feature MinMax-scaled matrix
  data/features_unit.npz          -- L2-normalised unit vectors (ground-truth k-NN)
  data/genres_onehot.npz          -- (N, 6) one-hot genre matrix
  data/metadata.csv               -- genre labels for silhouette
  ../backend/data/spotify_songs.csv -- raw acousticness values

Output
------
  results/04_ablation.csv
  figures/04_ablation/loo_delta.png   -- LOO feature importance chart
  figures/04_ablation/summary.png     -- all non-LOO experiments, audio vs +genre

Run from analysis/:
  python 04_feature_ablation.py
"""

import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import umap
from sklearn.manifold import trustworthiness
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import LabelEncoder, MinMaxScaler

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANALYSIS_DIR = Path(__file__).parent.parent.parent
DATA_DIR     = ANALYSIS_DIR / "data"
FIG_DIR      = ANALYSIS_DIR / "figures" / "04_ablation"
RESULTS_DIR  = ANALYSIS_DIR / "results"
CSV_PATH     = ANALYSIS_DIR / "../backend/data/spotify_songs.csv"

FEATURE_COLS = [
    "danceability", "energy", "loudness", "speechiness",
    "instrumentalness", "liveness", "valence", "tempo",
]

SAMPLE_N     = 3000
K_NEIGHBORS  = 10
RANDOM_STATE = 42
GENRE_WEIGHT = 0.3

UMAP_KWARGS = dict(
    n_components=3,
    metric="cosine",
    n_neighbors=40,
    min_dist=0.4,
    n_epochs=200,
    random_state=RANDOM_STATE,
    verbose=False,
)

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_data() -> tuple:
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

    # Load acousticness from CSV, aligned to the same row order as minmax_8
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    csv_df = (pd.read_csv(CSV_PATH, usecols=["track_id", "acousticness"])
               .drop_duplicates("track_id"))
    aligned = csv_df.set_index("track_id").reindex(meta["track_id"]).reset_index()
    acou_raw    = aligned["acousticness"].fillna(aligned["acousticness"].median()).to_numpy(dtype=np.float32).reshape(-1, 1)
    acou_scaled = MinMaxScaler().fit_transform(acou_raw).astype(np.float32)

    print(f"Loaded {len(minmax_8)} tracks")
    return minmax_8, unit_8, genre_onehot, acou_scaled, meta


# ---------------------------------------------------------------------------
# Build feature matrix
# ---------------------------------------------------------------------------

def build_matrix(
    minmax_8: np.ndarray,
    acou_scaled: np.ndarray,
    audio_cols: list[str],
    genre_onehot: np.ndarray | None = None,
) -> np.ndarray:
    """
    Constructs the UMAP input matrix.
    audio_cols may include any of FEATURE_COLS plus "acousticness".
    If genre_onehot is provided, it is appended scaled by GENRE_WEIGHT.
    """
    standard_idx = [FEATURE_COLS.index(c) for c in audio_cols if c in FEATURE_COLS]
    parts = [minmax_8[:, standard_idx]] if standard_idx else []
    if "acousticness" in audio_cols:
        parts.append(acou_scaled)
    X = np.concatenate(parts, axis=1)
    if genre_onehot is not None:
        X = np.concatenate([X, genre_onehot * GENRE_WEIGHT], axis=1)
    return X


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_gt_neighbors(unit: np.ndarray, idx: np.ndarray, k: int) -> np.ndarray:
    X = unit[idx]
    nn = NearestNeighbors(n_neighbors=k + 1, metric="cosine", n_jobs=-1).fit(X)
    _, nbrs = nn.kneighbors(X)
    return nbrs[:, 1:]


def knn_recall(coords_sub: np.ndarray, gt_nbrs: np.ndarray, k: int) -> float:
    nn = NearestNeighbors(n_neighbors=k + 1, metric="euclidean", n_jobs=-1).fit(coords_sub)
    _, nbrs = nn.kneighbors(coords_sub)
    nbrs = nbrs[:, 1:]
    return float(np.mean([
        len(set(gt_nbrs[i]) & set(nbrs[i])) / k
        for i in range(len(gt_nbrs))
    ]))


def compute_metrics(unit_sub, coords_sub, gt_nbrs, genre_sub) -> dict:
    trust  = trustworthiness(unit_sub, coords_sub, n_neighbors=K_NEIGHBORS, metric="cosine")
    recall = knn_recall(coords_sub, gt_nbrs, K_NEIGHBORS)
    sil    = silhouette_score(coords_sub, genre_sub, metric="euclidean",
                              sample_size=1000, random_state=RANDOM_STATE)
    return {
        "trustworthiness": round(trust,  4),
        "knn_recall":      round(recall, 4),
        "silhouette":      round(sil,    4),
    }


# ---------------------------------------------------------------------------
# Run one experiment
# ---------------------------------------------------------------------------

def normalize_coords(coords: np.ndarray) -> np.ndarray:
    lo = coords.min(axis=0)
    hi = coords.max(axis=0)
    return (coords - lo) / (hi - lo + 1e-9)


def run_experiment(name, X, unit_8, sample_idx, gt_nbrs, genre_sub) -> dict:
    t0 = time.time()
    reducer = umap.UMAP(**UMAP_KWARGS)
    coords  = normalize_coords(reducer.fit_transform(X).astype(np.float32))
    elapsed = time.time() - t0

    m = compute_metrics(unit_8[sample_idx], coords[sample_idx], gt_nbrs, genre_sub)
    m["name"]   = name
    m["time_s"] = round(elapsed, 1)
    print(f"  [{name:30s}] trust={m['trustworthiness']}  recall={m['knn_recall']}  sil={m['silhouette']}  ({elapsed:.1f}s)")
    return m


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_loo_delta(df: pd.DataFrame, baseline_trust: float, baseline_recall: float) -> None:
    loo = df[df["name"].str.startswith("loo_")].copy()
    loo["feature"]  = loo["name"].str.replace("loo_no_", "", regex=False)
    # importance = how much metrics drop when feature is removed (positive = important)
    loo["imp_trust"]  = baseline_trust   - loo["trustworthiness"]
    loo["imp_recall"] = baseline_recall  - loo["knn_recall"]
    loo = loo.sort_values("imp_recall", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Leave-One-Out Feature Importance\n(positive = removing this feature hurts)", fontsize=12)

    for ax, col, label, base_color in [
        (axes[0], "imp_trust",  "Δ Trustworthiness (baseline − LOO)", "#3498DB"),
        (axes[1], "imp_recall", "Δ k-NN Recall @10 (baseline − LOO)", "#E91E8C"),
    ]:
        colors = ["#2ECC71" if v > 0 else "#E74C3C" for v in loo[col]]
        ax.barh(loo["feature"], loo[col], color=colors, edgecolor="white")
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_xlabel(label)
        ax.set_title(label.split("(")[0].strip())

    fig.tight_layout()
    out = FIG_DIR / "loo_delta.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


def plot_summary(df: pd.DataFrame) -> None:
    summary = df[~df["name"].str.startswith("loo_")].copy().reset_index(drop=True)

    x     = np.arange(len(summary))
    width = 0.5

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Feature Set Comparison — Audio-only vs Audio+Genre", fontsize=12)

    for ax, col, label in [
        (axes[0], "trustworthiness", "Trustworthiness"),
        (axes[1], "knn_recall",      "k-NN Recall @10"),
    ]:
        bar_colors = ["#F39C12" if g else "#3498DB" for g in summary["genre_included"]]
        bars = ax.bar(x, summary[col], width, color=bar_colors, edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels(summary["name"], rotation=30, ha="right", fontsize=8)
        ax.set_ylabel(label)
        ax.set_title(label)
        ax.set_ylim(0, min(1.05, summary[col].max() * 1.15))
        for bar, val in zip(bars, summary[col]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=7)

    axes[0].legend(handles=[
        Patch(color="#3498DB", label="audio-only"),
        Patch(color="#F39C12", label="audio + genre"),
    ], fontsize=9)

    fig.tight_layout()
    out = FIG_DIR / "summary.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    minmax_8, unit_8, genre_onehot, acou_scaled, meta = load_data()

    rng        = np.random.default_rng(RANDOM_STATE)
    sample_idx = rng.choice(len(minmax_8), size=min(SAMPLE_N, len(minmax_8)), replace=False)
    genre_enc  = LabelEncoder().fit_transform(meta["playlist_genre"])
    genre_sub  = genre_enc[sample_idx]

    print(f"\nComputing ground-truth cosine k-NN (k={K_NEIGHBORS}) on {len(sample_idx)} subsample ...")
    gt_nbrs = compute_gt_neighbors(unit_8, sample_idx, K_NEIGHBORS)

    # ---- Define experiments ----
    swap_cols = [c for c in FEATURE_COLS if c != "loudness"] + ["acousticness"]

    # (name, audio_cols, genre_included)
    experiment_defs = (
        [("baseline",       FEATURE_COLS,                          False),
         ("baseline+genre", FEATURE_COLS,                          True)]
        + [(f"loo_no_{col}", [c for c in FEATURE_COLS if c != col], False)
           for col in FEATURE_COLS]
        + [("swap_loudness_acou", swap_cols,                        False),
           ("add_acousticness",   FEATURE_COLS + ["acousticness"],  False)]
    )

    print(f"\nRunning {len(experiment_defs)} experiments ...\n")

    results = []
    for name, audio_cols, genre_included in experiment_defs:
        X = build_matrix(minmax_8, acou_scaled, audio_cols,
                         genre_onehot if genre_included else None)
        m = run_experiment(name, X, unit_8, sample_idx, gt_nbrs, genre_sub)
        m["feature_set"]    = ", ".join(audio_cols)
        m["n_features"]     = len(audio_cols)
        m["genre_included"] = genre_included
        results.append(m)

    # ---- Determine best audio-only subset (non-baseline candidates) ----
    audio_candidates = [r for r in results if not r["genre_included"] and r["name"] != "baseline"]
    best = max(audio_candidates, key=lambda r: (r["trustworthiness"] + r["knn_recall"]) / 2)
    best_cols = best["feature_set"].split(", ")

    print(f"\nBest audio-only subset: '{best['name']}'  "
          f"(trust={best['trustworthiness']}, recall={best['knn_recall']})")

    if best["name"] != "baseline":
        print("  Running best subset + genre ...")
        X = build_matrix(minmax_8, acou_scaled, best_cols, genre_onehot)
        m = run_experiment(f"{best['name']}+genre", X, unit_8, sample_idx, gt_nbrs, genre_sub)
        m["feature_set"]    = best["feature_set"]
        m["n_features"]     = best["n_features"]
        m["genre_included"] = True
        results.append(m)
    else:
        print("  Best subset is baseline — genre comparison already included above.")

    # ---- Save ----
    cols_order = ["name", "feature_set", "n_features", "genre_included",
                  "trustworthiness", "knn_recall", "silhouette", "time_s"]
    df = pd.DataFrame(results)[cols_order]
    out_csv = RESULTS_DIR / "04_ablation.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {out_csv}")

    print("\n--- Results ---")
    print(df[["name", "n_features", "genre_included",
              "trustworthiness", "knn_recall", "silhouette"]].to_string(index=False))

    # ---- Plots ----
    print("\nGenerating plots ...")
    baseline_row = next(r for r in results if r["name"] == "baseline")
    plot_loo_delta(df, baseline_row["trustworthiness"], baseline_row["knn_recall"])
    plot_summary(df)

    # ---- Winner ----
    best_overall = df.loc[df[["trustworthiness", "knn_recall"]].mean(axis=1).idxmax()]
    print(f"\nBest overall: '{best_overall['name']}'  "
          f"trust={best_overall['trustworthiness']}  recall={best_overall['knn_recall']}")
    print("\nDone. Run 05_sweep.py next with the winning feature set.")


if __name__ == "__main__":
    main()
