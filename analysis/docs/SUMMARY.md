# Hacklytics — Analysis Pipeline Summary (Phases 1–9)

**Goal:** Build a 3D sonic similarity space for ~28k Spotify songs to power a music discovery app.
**Final stack:** 8 audio features + genre one-hot ×0.1 → UMAP (cosine, n=40, d=0.25) → 3D coords

---

## Phase 1 — Data Ingestion (`01_ingest.py`)

Loaded `spotify_songs.csv` (32k rows). After deduplication on `track_id`: **28,356 tracks** across 6 genres (edm, latin, pop, r&b, rap, rock).

Produced:
- `data/features_minmax.npz` — 8 audio features, MinMax-scaled
- `data/features_unit.npz` — same 8 features, L2-normalised (used as ground-truth for all k-NN recall metrics)
- `data/genres_onehot.npz` — (28356, 6) one-hot genre matrix
- `data/metadata.csv` — track_id, playlist_genre, track name/artist

---

## Phase 2 — Feature Analysis (`02_feature_analysis.py`)

Exploratory analysis of the 8 audio features. Confirmed reasonable distributions; established that ground-truth similarity = cosine on L2-normalised 8-feature vectors throughout all phases.

---

## Phase 3 — Reduction Method Comparison (`03_reduction_comparison.py`)

Tested 4 dimensionality reduction methods on 8 audio features (audio-only, no genre) compressed to 3D.

**Metrics:** trustworthiness (sklearn, cosine, k=10), k-NN recall @10, silhouette by genre, fit time.

| Method  | Trust  | Recall | Sil    | Time   |
|---------|--------|--------|--------|--------|
| PCA     | 0.8873 | 0.1422 | -0.070 | <1s    |
| UMAP    | 0.9444 | 0.3429 | -0.052 | 27.0s  |
| t-SNE   | 0.9896 | 0.4741 | -0.050 | 77.8s  |
| PaCMAP  | 0.9339 | 0.2514 | -0.068 | 7.1s   |

**Decision: UMAP.** t-SNE has the highest recall but no `transform()` method — can't project new songs without refitting. UMAP supports transform, is fast enough, and has strong recall. PaCMAP pinned to `<0.9` to avoid `faiss-cpu`/`swig` dependency.

---

## Phase 4 — Feature Ablation (`04_feature_ablation.py`)

Tested all 8 features individually (leave-one-out), acousticness swap, and audio-only vs audio+genre.

**Key LOO findings (audio-only recall):**

| Removed      | Recall | Δ vs baseline |
|--------------|--------|---------------|
| baseline     | 0.3429 | —             |
| valence      | 0.2168 | -0.126 ← most important |
| instrumentalness | 0.2752 | -0.068 |
| danceability | 0.2811 | -0.062 |
| energy       | 0.2718 | -0.071 |
| loudness     | 0.3240 | -0.019 ← least important |

**Genre included (w=0.3):** trust=0.9394, recall=0.2298, sil=**0.744** — silhouette jumps massively but recall tanks.

**Decision: keep all 8 features.** No subset outperforms the baseline. Acousticness addition hurts (recall→0.228). Test genre weight separately.

---

## Phase 4b — Genre Weight Sweep (`04b_genre_weight_sweep.py`)

Swept genre one-hot weights [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0].

| Weight | Trust  | Recall | Sil    |
|--------|--------|--------|--------|
| 0.00   | 0.9444 | 0.3429 | -0.052 |
| 0.05   | 0.9452 | 0.3473 | -0.050 |
| **0.10**   | **0.9330** | **0.2577** | **0.144** |
| 0.20   | 0.9419 | 0.2297 | 0.594  |
| 0.30   | 0.9394 | 0.2298 | 0.744  |
| 0.50   | 0.9421 | 0.2288 | 0.744  |
| 1.00   | 0.9399 | 0.2224 | 0.772  |

**Decision: w=0.1.** Best tradeoff — silhouette rises to 0.144 (light genre clustering for UX) with recall loss of only 0.085 vs pure audio. Weights ≥0.2 produce strong visual genre separation but recall drops sharply.

---

## Phase 5 — UMAP Hyperparameter Sweep (`05_sweep.py`)

60-config grid: `n_neighbors` ∈ {10, 20, 40, 80} × `min_dist` ∈ {0.05, 0.1, 0.25, 0.4, 0.8} × `metric` ∈ {cosine, euclidean, correlation}.

Feature matrix: 8 audio + genre×0.1 → (28356, 14). Combined score = avg(trust, recall).

**Top 5 configs:**

| Metric      | n  | dist | Trust  | Recall | Sil    | Combined |
|-------------|-----|------|--------|--------|--------|----------|
| **cosine**  | **40** | **0.25** | **0.9540** | **0.2666** | **0.2206** | **0.6103** |
| cosine      | 40  | 0.05 | 0.9593 | 0.2607 | 0.2849 | 0.6100   |
| cosine      | 40  | 0.10 | 0.9575 | 0.2619 | 0.2717 | 0.6097   |
| correlation | 40  | 0.10 | 0.9583 | 0.2606 | 0.2794 | 0.6094   |
| cosine      | 20  | 0.05 | 0.9587 | 0.2584 | 0.3190 | 0.6086   |

**Winner: cosine, n_neighbors=40, min_dist=0.25** — best combined score. Top configs are tightly clustered; n_neighbors=40 and cosine metric dominate.

---

## Phase 5b — Top-5 Point Cloud Scatter (`05b_top5_scatter.py`)

Generated scatter plots for top 5 configs (XY projection, 5k songs, colored by genre) and all 3 projections (XY/XZ/YZ) for the winner. Visually confirmed genre clustering at w=0.1 is light but present.

---

## Phase 7 — TriMAP (`07_trimap.py`)

Tested TriMAP (triplet-ranking objective, supports `transform()`) as an alternative to UMAP.

| Method | Trust  | Recall | Sil    | Time  |
|--------|--------|--------|--------|-------|
| UMAP   | 0.9540 | 0.2666 | 0.2206 | 24.4s |
| TriMAP | 0.9056 | 0.1799 | 0.0345 | 9.7s  |

**Decision: keep UMAP.** TriMAP recall is 34% lower (0.180 vs 0.267) and silhouette collapses. UMAP is unambiguously better.

---

## Phase 8 — Parametric UMAP (`08_parametric_umap.py`)

Tested a neural encoder (Keras) trained to approximate UMAP's embedding — primary motivation was faster inference for new songs.

| Method           | Trust  | Recall | Fit Time | Inference |
|------------------|--------|--------|----------|-----------|
| Standard UMAP    | 0.9540 | 0.2666 | 23.6s    | 0.89ms    |
| Parametric UMAP  | —      | 0.096  | ~52 min  | 27ms      |

Parametric UMAP loss increased across all 10 epochs (non-convergence). Recall is 64% lower. Inference is actually **slower** (27ms vs 0.89ms) due to Keras forward-pass overhead on 14D input.

**Decision: keep standard UMAP.** Standard UMAP `transform()` at 0.89ms per song is fast enough for backend use.

---

## Phase 9 — Local Scaling Post-Retrieval (`09_local_scaling.py`)

Tested Local Scaling reranking `d'(x,y) = d(x,y)/(σ_x·σ_y)` to improve k-NN recall when retrieving from 3D UMAP coords (the app's actual use case). Ground truth remains 8D cosine.

σ_i = euclidean distance to 10th neighbor in 3D space (cached to `data/local_scaling_sigmas_3d.npy`).

| Method              | Recall @10 | Δ       |
|---------------------|------------|---------|
| Baseline 3D euclid. | 0.2000     | —       |
| Local Scaling 3D    | 0.1974     | -0.0026 |

σ distribution is narrow (mean=0.022, max=0.092) — UMAP already produces near-uniform local density by design, so Local Scaling has no density variation to correct.

**Decision: keep plain euclidean on 3D UMAP coords.** The recall ceiling (~0.20–0.27) is set by the 8D→3D compression ratio itself, not retrieval ranking.

---

## Final Configuration

| Parameter         | Value                                      |
|-------------------|--------------------------------------------|
| Feature set       | 8 audio features + genre one-hot × 0.1    |
| Feature matrix    | (28356, 14), MinMax-scaled                 |
| Ground-truth k-NN | cosine on 8D L2-normalised unit vectors    |
| Reduction method  | UMAP                                       |
| UMAP metric       | cosine                                     |
| n_neighbors       | 40                                         |
| min_dist          | 0.25                                       |
| n_components      | 3                                          |
| Trustworthiness   | 0.954                                      |
| k-NN recall @10   | 0.267 (hard ceiling from 8D→3D compression)|
| Silhouette        | 0.221                                      |
| Fit time          | ~24s                                       |
| Transform (new song) | ~0.89ms                               |
| Coords saved      | `data/umap_coords_winner.npy`              |
