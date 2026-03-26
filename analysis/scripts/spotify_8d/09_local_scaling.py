"""
Local Scaling Post-Retrieval Reranking (3D UMAP Embedding)
=============================================
Evaluates whether Local Scaling reranking improves k-NN recall @10
when using 3D UMAP coordinates for similarity (the app's use case).

Setup
-----
- Ground truth   : cosine k-NN on 8D L2-normalised unit vectors
- Retrieval space: euclidean k-NN on 3D UMAP coords (winner config)
- Reranking      : d'(x,y) = d(x,y) / (σ_x · σ_y)
                   where σ_i = euclidean dist to K_SIGMA-th neighbor in 3D space

Also tests Mutual Proximity if Local Scaling gains ≥ +0.03 recall.

Run from analysis/:
  python 09_local_scaling.py
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import umap
from sklearn.neighbors import NearestNeighbors

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANALYSIS_DIR = Path(__file__).parent.parent.parent
DATA_DIR     = ANALYSIS_DIR / "data"
RESULTS_DIR  = ANALYSIS_DIR / "results"

# Winner config from Phase 5 sweep
UMAP_METRIC     = "cosine"
UMAP_N_NEIGHBORS = 40
UMAP_MIN_DIST   = 0.25
GENRE_WEIGHT    = 0.1
RANDOM_STATE    = 42

K_SIGMA      = 10    # σ_i = dist to k-th neighbor in 3D space
K_RECALL     = 10    # recall metric
CANDIDATES   = 30    # candidate pool before reranking
N_QUERIES    = 500   # held-out query songs

COORDS_PATH = DATA_DIR / "umap_coords_winner.npy"
SIGMA_PATH  = DATA_DIR / "local_scaling_sigmas_3d.npy"

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_data():
    for p in [DATA_DIR / "features_minmax.npz", DATA_DIR / "features_unit.npz",
              DATA_DIR / "genres_onehot.npz"]:
        if not p.exists():
            print(f"ERROR: {p} not found.", file=sys.stderr)
            sys.exit(1)

    minmax_8     = np.load(DATA_DIR / "features_minmax.npz", allow_pickle=True)["features"]
    unit_8       = np.load(DATA_DIR / "features_unit.npz",   allow_pickle=True)["features"]
    genre_onehot = np.load(DATA_DIR / "genres_onehot.npz",   allow_pickle=True)["features"]

    X = np.concatenate([minmax_8, genre_onehot * GENRE_WEIGHT], axis=1)
    print(f"Loaded {len(unit_8)} tracks  |  feature matrix: {X.shape}  |  unit: {unit_8.shape}")
    return X, unit_8


# ---------------------------------------------------------------------------
# UMAP fit / cache
# ---------------------------------------------------------------------------

def normalize_coords(coords):
    lo = coords.min(axis=0)
    hi = coords.max(axis=0)
    return (coords - lo) / (hi - lo + 1e-9)


def get_umap_coords(X) -> np.ndarray:
    if COORDS_PATH.exists():
        print(f"\nLoading cached 3D UMAP coords from {COORDS_PATH}")
        return np.load(COORDS_PATH)

    print(f"\nFitting UMAP (metric={UMAP_METRIC}, n_neighbors={UMAP_N_NEIGHBORS}, "
          f"min_dist={UMAP_MIN_DIST}) ...")
    t0 = time.time()
    reducer = umap.UMAP(
        n_components=3,
        metric=UMAP_METRIC,
        n_neighbors=UMAP_N_NEIGHBORS,
        min_dist=UMAP_MIN_DIST,
        n_epochs=200,
        random_state=RANDOM_STATE,
        verbose=False,
    )
    coords = normalize_coords(reducer.fit_transform(X).astype(np.float32))
    print(f"Fit done in {time.time() - t0:.1f}s")
    np.save(COORDS_PATH, coords)
    print(f"Saved {COORDS_PATH}")
    return coords


# ---------------------------------------------------------------------------
# Sigmas in 3D euclidean space
# ---------------------------------------------------------------------------

def get_sigmas(coords: np.ndarray) -> np.ndarray:
    if SIGMA_PATH.exists():
        print(f"\nLoading cached 3D sigmas from {SIGMA_PATH}")
        return np.load(SIGMA_PATH)

    print(f"\nComputing σ (euclidean dist to {K_SIGMA}th neighbor in 3D) ...")
    nn = NearestNeighbors(n_neighbors=K_SIGMA + 1, metric="euclidean", n_jobs=-1).fit(coords)
    dists, _ = nn.kneighbors(coords)
    sigmas = np.maximum(dists[:, K_SIGMA].astype(np.float32), 1e-9)
    np.save(SIGMA_PATH, sigmas)
    print(f"Saved {SIGMA_PATH}")
    return sigmas


# ---------------------------------------------------------------------------
# Ground-truth k-NN (8D cosine)
# ---------------------------------------------------------------------------

def compute_gt_neighbors(unit: np.ndarray, query_idx: np.ndarray, k: int) -> np.ndarray:
    nn = NearestNeighbors(n_neighbors=k + 1, metric="cosine", n_jobs=-1).fit(unit)
    _, nbrs = nn.kneighbors(unit[query_idx])
    return nbrs[:, 1:]


# ---------------------------------------------------------------------------
# 3D euclidean retrieval
# ---------------------------------------------------------------------------

def retrieve_candidates_3d(coords: np.ndarray, query_idx: np.ndarray,
                            n_candidates: int) -> tuple[np.ndarray, np.ndarray]:
    nn = NearestNeighbors(n_neighbors=n_candidates + 1, metric="euclidean", n_jobs=-1).fit(coords)
    dists, nbrs = nn.kneighbors(coords[query_idx])
    return nbrs[:, 1:], dists[:, 1:]   # drop self


def recall_at_k(top_k_indices: np.ndarray, gt_nbrs: np.ndarray, k: int) -> float:
    return float(np.mean([
        len(set(gt_nbrs[i]) & set(top_k_indices[i])) / k
        for i in range(len(gt_nbrs))
    ]))


# ---------------------------------------------------------------------------
# Reranking strategies
# ---------------------------------------------------------------------------

def rerank_local_scaling(cand_idx: np.ndarray, cand_dists: np.ndarray,
                         sigmas: np.ndarray, query_idx: np.ndarray,
                         k: int) -> np.ndarray:
    """d'(x, y) = d(x, y) / (σ_x · σ_y)"""
    n     = len(query_idx)
    top_k = np.empty((n, k), dtype=np.int64)
    for i in range(n):
        q_sigma  = sigmas[query_idx[i]]
        c_sigmas = sigmas[cand_idx[i]]
        scaled   = cand_dists[i] / (q_sigma * c_sigmas)
        order    = np.argsort(scaled)[:k]
        top_k[i] = cand_idx[i][order]
    return top_k


def rerank_mutual_proximity(cand_idx: np.ndarray, cand_dists: np.ndarray,
                             local_dists: np.ndarray, query_idx: np.ndarray,
                             k: int) -> np.ndarray:
    """
    Empirical Mutual Proximity reranking.
    MP(x,y) = (1 - F_x(d(x,y))) * (1 - F_y(d(x,y)))
    F estimated from each point's local neighborhood distances.
    """
    n     = len(query_idx)
    top_k = np.empty((n, k), dtype=np.int64)
    for i in range(n):
        qi   = query_idx[i]
        ci   = cand_idx[i]
        d    = cand_dists[i]

        # Fraction of qi's local neighbors closer than d(qi, cj)
        F_x = np.mean(local_dists[qi][None, :] < d[:, None], axis=1)
        # Same for each candidate
        F_y = np.array([np.mean(local_dists[ci[j]] < d[j]) for j in range(len(ci))])

        mp_score = (1.0 - F_x) * (1.0 - F_y)
        order    = np.argsort(-mp_score)[:k]
        top_k[i] = ci[order]
    return top_k


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    RESULTS_DIR.mkdir(exist_ok=True)

    X, unit_8 = load_data()

    # ---- 3D UMAP coords ----
    coords = get_umap_coords(X)
    print(f"3D coords shape: {coords.shape}  range: [{coords.min():.3f}, {coords.max():.3f}]")

    # ---- Sigmas in 3D space ----
    sigmas = get_sigmas(coords)
    print(f"σ stats — mean={sigmas.mean():.4f}  median={np.median(sigmas):.4f}  "
          f"min={sigmas.min():.6f}  max={sigmas.max():.4f}")

    # ---- Hold-out query set ----
    rng       = np.random.default_rng(RANDOM_STATE)
    query_idx = rng.choice(len(unit_8), size=N_QUERIES, replace=False).astype(np.int64)

    # ---- Ground-truth (8D cosine) ----
    print(f"\nComputing ground-truth cosine k-NN (k={K_RECALL}) for {N_QUERIES} queries ...")
    gt_nbrs = compute_gt_neighbors(unit_8, query_idx, K_RECALL)

    # ---- 3D euclidean retrieval ----
    print(f"Retrieving top-{CANDIDATES} candidates per query (3D euclidean) ...")
    cand_idx, cand_dists = retrieve_candidates_3d(coords, query_idx, CANDIDATES)

    # Baseline: top-K_RECALL from raw 3D euclidean
    baseline_top_k  = cand_idx[:, :K_RECALL]
    baseline_recall = recall_at_k(baseline_top_k, gt_nbrs, K_RECALL)
    print(f"\nBaseline 3D euclidean recall @{K_RECALL}: {baseline_recall:.4f}")

    # ---- Local Scaling ----
    print("Applying Local Scaling reranking ...")
    ls_top_k  = rerank_local_scaling(cand_idx, cand_dists, sigmas, query_idx, K_RECALL)
    ls_recall = recall_at_k(ls_top_k, gt_nbrs, K_RECALL)
    ls_delta  = ls_recall - baseline_recall
    print(f"Local Scaling recall @{K_RECALL}:  {ls_recall:.4f}  (Δ={ls_delta:+.4f})")

    results = [
        {"method": "baseline_3d_euclidean", "recall_at_10": round(baseline_recall, 4), "delta": 0.0},
        {"method": "local_scaling_3d",      "recall_at_10": round(ls_recall, 4),       "delta": round(ls_delta, 4)},
    ]

    # ---- Mutual Proximity (if LS gains ≥ +0.03) ----
    if ls_delta >= 0.03:
        print(f"\nLocal Scaling gained {ls_delta:+.4f} ≥ +0.03 — testing Mutual Proximity ...")
        # Precompute local neighborhood distances for MP (reuse sigma neighbors)
        nn_mp = NearestNeighbors(n_neighbors=K_SIGMA + 1, metric="euclidean", n_jobs=-1).fit(coords)
        mp_dists, _ = nn_mp.kneighbors(coords)
        local_dists = mp_dists[:, 1:]   # drop self

        mp_top_k  = rerank_mutual_proximity(cand_idx, cand_dists, local_dists, query_idx, K_RECALL)
        mp_recall = recall_at_k(mp_top_k, gt_nbrs, K_RECALL)
        mp_delta  = mp_recall - baseline_recall
        print(f"Mutual Proximity recall @{K_RECALL}: {mp_recall:.4f}  (Δ={mp_delta:+.4f})")
        results.append({"method": "mutual_proximity_3d", "recall_at_10": round(mp_recall, 4),
                         "delta": round(mp_delta, 4)})
    else:
        print(f"\nLocal Scaling gain {ls_delta:+.4f} < +0.03 — skipping Mutual Proximity.")

    # ---- Save ----
    df = pd.DataFrame(results)
    out_csv = RESULTS_DIR / "09_local_scaling_eval.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {out_csv}")

    print("\n--- Summary ---")
    print(df.to_string(index=False))

    best = df.loc[df["recall_at_10"].idxmax()]
    print(f"\nBest method: {best['method']}  recall={best['recall_at_10']}  Δ={best['delta']:+.4f}")
    if best["method"] == "baseline_3d_euclidean":
        print("→ Local Scaling does not improve 3D retrieval. Keep plain euclidean on UMAP coords.")
    elif best["delta"] >= 0.03:
        print(f"→ Significant gain (+{best['delta']:.4f}). Recommend integrating {best['method']} into backend.")
    else:
        print(f"→ Marginal gain (+{best['delta']:.4f}). Likely not worth the added latency.")

    print("\nDone.")


if __name__ == "__main__":
    main()
