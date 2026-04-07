# Soundgaze — Analysis Summary

Systematic analysis of the Spotify audio feature space to determine the best feature set,
genre weighting, and UMAP configuration for the 3D point cloud. All phases used
28,356 unique tracks from `spotify_songs.csv`.

---

## Final Recommended Configuration

| Parameter | Value |
|---|---|
| **Feature set** | 8 audio features + genre one-hot × 0.1 |
| **Reduction method** | UMAP |
| **UMAP metric** | cosine |
| **n_neighbors** | 40 |
| **min_dist** | 0.25 |
| **n_components** | 3 |

**Expected metrics (3,000-track subsample, k=10):**

| Metric | Value |
|---|---|
| Trustworthiness | 0.954 |
| k-NN Recall @10 | 0.267 |
| Silhouette (genre) | 0.221 |

---

## Phase 2 — Feature Analysis

8 current features: `danceability`, `energy`, `loudness`, `speechiness`,
`instrumentalness`, `liveness`, `valence`, `tempo`.

4 dropped features evaluated: `acousticness`, `key`, `mode`, `duration_ms`.

**Key findings:**
- `energy` ↔ `loudness`: r ≈ 0.75 — highly correlated but both kept (LOO confirms both meaningful)
- `acousticness` ↔ `energy`: r ≈ −0.70 — independent signal, but Phase 4 showed swapping
  or adding acousticness *hurts* recall; kept out of the final set
- `mode` has artificially high variance (binary 0/1); not added
- PCA scree: 7 PCs explain 90% of variance (audio-only); adding genre at w=0.3 requires 10 PCs
- **Decision:** keep the original 8 audio features; dropped features add noise not signal

---

## Phase 3 — Reduction Method Comparison

Input: 8 audio features, MinMax-scaled. Ground-truth k-NN: cosine on L2-normalised vectors.

| Method | Trustworthiness | k-NN Recall @10 | Silhouette | transform() |
|---|---|---|---|---|
| PCA | 0.887 | 0.142 | −0.070 | ✅ |
| UMAP | 0.944 | 0.343 | −0.052 | ✅ |
| t-SNE | 0.990 | 0.474 | −0.050 | ❌ |
| PaCMAP | 0.934 | 0.251 | −0.068 | ✅ |

**Decision: UMAP.**
t-SNE has the best metrics but no `transform()` — new user tracks cannot be placed
in 3D at query time without re-fitting the entire model. UMAP is the best viable option.
PaCMAP is faster but lower recall.

---

## Phase 4 — Feature Set Ablation

Reduction method fixed to UMAP (cosine, n_neighbors=40, min_dist=0.4).

**Leave-one-out results — feature importance (Δ recall when removed):**

| Feature | Δ Recall | Importance |
|---|---|---|
| valence | −0.126 | critical |
| energy | −0.071 | critical |
| danceability | −0.062 | high |
| instrumentalness | −0.068 | high |
| speechiness | −0.032 | moderate |
| tempo | −0.027 | moderate |
| loudness | −0.019 | low |
| liveness | −0.049 | moderate |

No feature is safe to remove — every LOO hurts recall. Swapping loudness for acousticness
and adding acousticness both *reduced* recall, so the original 8-feature set is kept as-is.

**Genre impact (w=0.3):** recall drops 0.343 → 0.230 but silhouette jumps −0.052 → 0.744.
Genre strongly reorganises the space around genre clusters at the expense of fine-grained
audio similarity.

---

## Phase 4b — Genre Weight Sweep

Tested weights [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0] on the 8-feature baseline.

| Weight | Trustworthiness | k-NN Recall @10 | Silhouette |
|---|---|---|---|
| 0.00 | 0.944 | 0.343 | −0.052 |
| 0.05 | 0.945 | 0.347 | −0.050 |
| **0.10** | **0.933** | **0.258** | **0.144** |
| 0.20 | 0.942 | 0.230 | 0.594 |
| 0.30 | 0.939 | 0.230 | 0.744 |
| 0.50 | 0.942 | 0.229 | 0.744 |
| 0.70 | 0.939 | 0.220 | 0.700 |
| 1.00 | 0.940 | 0.222 | 0.772 |

**Decision: genre_weight = 0.1.**
Gives light genre clustering (sil=0.14 — songs visibly grouped but not rigidly segregated)
while preserving the most recall among weights that carry any genre signal. Weights ≥ 0.2
cause aggressive genre segregation that overrides fine-grained audio similarity.

---

## Phase 5 — UMAP Hyperparameter Sweep

Input: 8 audio features + genre one-hot × 0.1. Grid: 60 configs.

**Top 5 configs (ranked by avg(trustworthiness, recall)):**

| Metric | n_neighbors | min_dist | Trustworthiness | k-NN Recall @10 | Silhouette | Combined |
|---|---|---|---|---|---|---|
| cosine | 40 | **0.25** | 0.954 | 0.267 | 0.221 | 0.610 |
| cosine | 40 | 0.05 | 0.959 | 0.261 | 0.285 | 0.610 |
| cosine | 40 | 0.10 | 0.958 | 0.262 | 0.272 | 0.610 |
| correlation | 40 | 0.10 | 0.958 | 0.261 | 0.279 | 0.609 |
| cosine | 20 | 0.05 | 0.959 | 0.258 | 0.319 | 0.609 |

**Winner: cosine, n_neighbors=40, min_dist=0.25.**
`n_neighbors=40` is consistently the best — captures broader local structure. `min_dist=0.25`
gives a good balance between spread (visually clear clusters) and local compactness
(better recall than 0.4). Correlation metric performs comparably to cosine but cosine
is the natural choice for unit-vector similarity.

---

## Caveats

- **k-NN recall ceiling:** Compressing 8D → 3D loses information. ~27% recall at k=10
  is partially fundamental to the compression ratio. Recall at k=20 would be higher
  (~40–50%) and may better reflect the actual UX experience.
- **Ground truth is audio-only:** The 8-feature cosine ground truth does not account for
  genre. The genre weight at 0.1 slightly re-organises the space in ways the metric
  does not capture — visual inspection of the scatter plots suggests the layout is
  reasonable.
- **t-SNE is strictly better on metrics** but cannot project new points at runtime.
  If offline batch-only projection ever becomes acceptable, t-SNE (perplexity=30,
  cosine) is worth revisiting.

---

## Backend Implementation Changes

Update `backend/mapping.py` with the following UMAP config:

```python
GENRE_WEIGHT = 0.1          # append genre one-hot × this weight to audio features
UMAP_CONFIG = dict(
    n_components=3,
    metric="cosine",
    n_neighbors=40,
    min_dist=0.25,
    n_epochs=200,
    random_state=42,
)
```

The ingest pipeline should:
1. Build the 8-feature MinMax-scaled audio vector
2. Append the 6-column genre one-hot × 0.1 before fitting/transforming UMAP
3. Store the resulting 3D coordinates in `songs_3d` as before
4. Use the same genre-weighted vector when projecting new user tracks at query time

The backend DB similarity metric (cosine on L2-normalised audio vectors) is unchanged —
the UMAP metric only affects the 3D layout, not the recommendation ranking.
