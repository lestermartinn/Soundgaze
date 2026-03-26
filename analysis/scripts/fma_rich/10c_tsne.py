"""
t-SNE comparison on FMA 518D librosa features.

Pipeline: features.csv (518D) → StandardScaler → PCA 213D → t-SNE 3D
Metrics:  trustworthiness @10, k-NN recall @10

Compares directly against UMAP results from 10b (recall=0.0618, trust=0.8689).
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd
from openTSNE import TSNE
from sklearn.decomposition import PCA
from sklearn.manifold import trustworthiness
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR  = Path(__file__).parent.parent.parent / "data"
META_DIR  = DATA_DIR / "fma_metadata"
RESULTS   = Path(__file__).parent.parent.parent / "results"

N_COMPONENTS_PCA = 213
PERPLEXITY       = 40    # comparable to UMAP n_neighbors=40
K                = 10
N_QUERIES        = 500
RANDOM_STATE     = 42

# ---------------------------------------------------------------------------
# Load + preprocess  (same as 10b)
# ---------------------------------------------------------------------------
print("Loading features.csv ...")
features = pd.read_csv(META_DIR / "features.csv", index_col=0, header=[0, 1, 2]).dropna()
tracks   = pd.read_parquet(DATA_DIR / "fma_tracks.parquet")
features = features.loc[features.index.isin(tracks.index)]
print(f"  {features.shape[0]} tracks")

X_scaled = StandardScaler().fit_transform(features.values)

print(f"PCA → {N_COMPONENTS_PCA}D ...")
X_pca = PCA(n_components=N_COMPONENTS_PCA, random_state=RANDOM_STATE).fit_transform(X_scaled).astype(np.float32)

# ---------------------------------------------------------------------------
# t-SNE → 3D
# ---------------------------------------------------------------------------
print(f"\nFitting t-SNE 3D (perplexity={PERPLEXITY}) ...")
t0 = time.time()
tsne = TSNE(
    n_components=3,
    perplexity=PERPLEXITY,
    metric="cosine",
    negative_gradient_method="bh",   # FFT only supports 2D; Barnes-Hut supports 3D
    n_jobs=-1,
    random_state=RANDOM_STATE,
    verbose=True,
)
X_3d = tsne.fit(X_pca).astype(np.float32)
fit_time = time.time() - t0
print(f"Done in {fit_time:.1f}s  |  shape: {X_3d.shape}")

# ---------------------------------------------------------------------------
# Ground-truth k-NN on 213D PCA (cosine) — same as 10b
# ---------------------------------------------------------------------------
N = len(X_pca)
rng = np.random.default_rng(RANDOM_STATE)
query_idx = rng.choice(N, size=min(N_QUERIES, N), replace=False)

print(f"\nComputing ground-truth cosine k-NN (k={K}) for {len(query_idx)} queries ...")
gt_nn = NearestNeighbors(n_neighbors=K + 1, metric="cosine", n_jobs=-1).fit(X_pca)
_, gt_idx = gt_nn.kneighbors(X_pca[query_idx])
gt_neighbors = gt_idx[:, 1:]

print("Retrieving top-30 candidates per query (3D euclidean) ...")
nn_3d = NearestNeighbors(n_neighbors=31, metric="euclidean", n_jobs=-1).fit(X_3d)
_, cand_idx = nn_3d.kneighbors(X_3d[query_idx])
cand_neighbors = cand_idx[:, 1:K+1]

recall = sum(
    len(set(gt_neighbors[i]) & set(cand_neighbors[i]))
    for i in range(len(query_idx))
) / (len(query_idx) * K)

print("Computing trustworthiness ...")
sub_idx = rng.choice(N, size=min(3000, N), replace=False)
trust = trustworthiness(X_pca[sub_idx], X_3d[sub_idx], n_neighbors=K, metric="cosine")

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
print(f"\n{'='*55}")
print(f"  Tracks          : {N}")
print(f"  Fit time        : {fit_time:.1f}s")
print(f"  Trustworthiness : {trust:.4f}  (UMAP: 0.8689)")
print(f"  Recall @{K}       : {recall:.4f}  (UMAP: 0.0618)")
print(f"{'='*55}")

results = pd.DataFrame([{
    "method":       "fma_rich_518D_pca213_tsne3D",
    "n_tracks":     N,
    "trust":        round(trust, 4),
    "recall_at_10": round(recall, 4),
    "umap_recall":  0.0618,
    "umap_trust":   0.8689,
    "fit_sec":      round(fit_time, 1),
}])
out = RESULTS / "10c_tsne.csv"
results.to_csv(out, index=False)
print(f"\nSaved → {out}")
