"""
FMA Rich Features Evaluation

Pipeline: features.csv (518D) → StandardScaler → PCA 32D → UMAP 3D
Metrics:  trustworthiness @10, k-NN recall @10

Ground truth: cosine k-NN on PCA 32D features (pre-UMAP).
Baseline to beat: Phase 5 recall=0.267, trust=0.954
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors
from sklearn.manifold import trustworthiness
from sklearn.preprocessing import StandardScaler
import umap

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR   = Path(__file__).parent.parent.parent / "data"
META_DIR   = DATA_DIR / "fma_metadata"
RESULTS    = Path(__file__).parent.parent.parent / "results"
RESULTS.mkdir(exist_ok=True)

N_COMPONENTS_PCA = 213
N_NEIGHBORS_UMAP = 40
MIN_DIST         = 0.25
METRIC           = "cosine"
RANDOM_STATE     = 42
K                = 10       # recall @K
N_QUERIES        = 500
GT_K             = 30       # ground-truth candidates pool

# ---------------------------------------------------------------------------
# Load features.csv  (518D, pre-extracted librosa)
# ---------------------------------------------------------------------------
print("Loading features.csv ...")
features = pd.read_csv(META_DIR / "features.csv", index_col=0, header=[0, 1, 2])
print(f"  Raw shape: {features.shape}")

# Load genre labels from saved parquet
tracks = pd.read_parquet(DATA_DIR / "fma_tracks.parquet")
valid_ids = tracks.index  # tracks with a genre label

# Filter to tracks that have genre AND have no NaN in features
features = features.loc[features.index.isin(valid_ids)]
features = features.dropna()
print(f"  After genre + NaN filter: {features.shape[0]} tracks")

genre_labels = tracks.loc[features.index, "genre"]
print(f"  Genre distribution:\n{genre_labels.value_counts().to_string()}")

X_raw = features.values.astype(np.float32)

# ---------------------------------------------------------------------------
# StandardScaler  (features span very different ranges)
# ---------------------------------------------------------------------------
print("\nStandardScaling ...")
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_raw)

# ---------------------------------------------------------------------------
# PCA → 32D
# ---------------------------------------------------------------------------
print(f"PCA → {N_COMPONENTS_PCA}D ...")
pca = PCA(n_components=N_COMPONENTS_PCA, random_state=RANDOM_STATE)
X_pca = pca.fit_transform(X_scaled).astype(np.float32)
var_explained = pca.explained_variance_ratio_.sum() * 100
print(f"  Variance explained by {N_COMPONENTS_PCA} components: {var_explained:.1f}%")

# ---------------------------------------------------------------------------
# UMAP → 3D
# ---------------------------------------------------------------------------
print(f"\nFitting UMAP (metric={METRIC}, n_neighbors={N_NEIGHBORS_UMAP}, min_dist={MIN_DIST}) ...")
t0 = time.time()
reducer = umap.UMAP(
    n_components=3,
    metric=METRIC,
    n_neighbors=N_NEIGHBORS_UMAP,
    min_dist=MIN_DIST,
    random_state=RANDOM_STATE,
    n_jobs=1,
)
X_3d = reducer.fit_transform(X_pca).astype(np.float32)
fit_time = time.time() - t0
print(f"  Done in {fit_time:.1f}s  |  3D shape: {X_3d.shape}")

# ---------------------------------------------------------------------------
# Ground-truth k-NN on PCA 32D (cosine)
# ---------------------------------------------------------------------------
N = len(X_pca)
rng = np.random.default_rng(RANDOM_STATE)
query_idx = rng.choice(N, size=min(N_QUERIES, N), replace=False)

print(f"\nComputing ground-truth cosine k-NN (k={K}) for {len(query_idx)} queries ...")
gt_nn = NearestNeighbors(n_neighbors=K + 1, metric="cosine", n_jobs=-1)
gt_nn.fit(X_pca)
gt_distances, gt_indices = gt_nn.kneighbors(X_pca[query_idx])
gt_neighbors = gt_indices[:, 1:]  # exclude self

# ---------------------------------------------------------------------------
# Retrieve from 3D euclidean
# ---------------------------------------------------------------------------
print(f"Retrieving top-{GT_K} candidates per query (3D euclidean) ...")
nn_3d = NearestNeighbors(n_neighbors=GT_K + 1, metric="euclidean", n_jobs=-1)
nn_3d.fit(X_3d)
_, cand_indices = nn_3d.kneighbors(X_3d[query_idx])
cand_neighbors = cand_indices[:, 1:K+1]  # top-K from 3D

# ---------------------------------------------------------------------------
# k-NN Recall @K
# ---------------------------------------------------------------------------
hits = sum(
    len(set(gt_neighbors[i]) & set(cand_neighbors[i]))
    for i in range(len(query_idx))
)
recall = hits / (len(query_idx) * K)

# ---------------------------------------------------------------------------
# Trustworthiness (subsample for speed)
# ---------------------------------------------------------------------------
print("Computing trustworthiness ...")
sub_n = min(3000, N)
sub_idx = rng.choice(N, size=sub_n, replace=False)
trust = trustworthiness(X_pca[sub_idx], X_3d[sub_idx], n_neighbors=K, metric="cosine")

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
print(f"\n{'='*50}")
print(f"  Tracks          : {N}")
print(f"  PCA variance    : {var_explained:.1f}%")
print(f"  UMAP fit time   : {fit_time:.1f}s")
print(f"  Trustworthiness : {trust:.4f}  (Phase 5 baseline: 0.954)")
print(f"  Recall @{K}       : {recall:.4f}  (Phase 5 baseline: 0.267)")
print(f"{'='*50}")

delta_recall = recall - 0.267
delta_trust  = trust  - 0.954
print(f"\n  Δ recall vs Phase 5 baseline: {delta_recall:+.4f}")
print(f"  Δ trust  vs Phase 5 baseline: {delta_trust:+.4f}")

if delta_recall >= 0.05:
    print("\n  → Rich features improve recall ≥ +0.05. Proceed to Phase 11.")
elif delta_recall >= 0:
    print("\n  → Modest improvement. Consider Phase 11 before concluding.")
else:
    print("\n  → No improvement over baseline. Feature quality may not be the bottleneck.")

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
results = pd.DataFrame([{
    "method":        "fma_rich_518D_pca32_umap3D",
    "n_tracks":      N,
    "pca_variance":  round(var_explained, 2),
    "trust":         round(trust, 4),
    "recall_at_10":  round(recall, 4),
    "delta_recall":  round(delta_recall, 4),
    "umap_fit_sec":  round(fit_time, 1),
    "phase5_recall": 0.267,
    "phase5_trust":  0.954,
}])
out = RESULTS / "10b_fma_eval.csv"
results.to_csv(out, index=False)
print(f"\nSaved → {out}")
