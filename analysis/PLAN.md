# Music Feature Analysis Plan

## Goal

Determine the best set of features and reduction method to produce a 3D space where
proximity = sonic similarity. Currently: 8 raw features → cosine similarity → UMAP 3D.

---

## Available Features (from spotify_songs.csv)

| Feature | Type | Range | Currently Used |
|---|---|---|---|
| danceability | continuous | [0, 1] | ✅ |
| energy | continuous | [0, 1] | ✅ |
| loudness | continuous | dB (neg) | ✅ (normalized) |
| speechiness | continuous | [0, 1] | ✅ |
| instrumentalness | continuous | [0, 1] | ✅ |
| liveness | continuous | [0, 1] | ✅ |
| valence | continuous | [0, 1] | ✅ |
| tempo | continuous | BPM | ✅ (normalized) |
| acousticness | continuous | [0, 1] | ❌ dropped |
| key | categorical (0–11) | discrete | ❌ dropped |
| mode | binary (0 or 1) | discrete | ❌ dropped |
| duration_ms | continuous | ms | ❌ dropped |

---

## Phase 1: Data Ingestion (`01_ingest.py`)

Load and clean `spotify_songs.csv` into a ready-to-use DataFrame for all downstream
analysis. Mirror the backend's normalization pipeline exactly so results are comparable.

Steps:
1. Read CSV with pandas
2. Drop NaN rows and duplicate `track_id`s
3. Produce three versions of the feature matrix:
   - **raw** — original values, no scaling
   - **minmax** — MinMaxScaler per feature to [0, 1]
   - **unit** — L2-normalized rows (matches backend's actual vector representation)
4. Save outputs:
   - `data/features_raw.npz`
   - `data/features_minmax.npz`
   - `data/features_unit.npz`
   - `data/metadata.parquet` — track_id, name, artist, genre for labeling plots

---

## Phase 2: Feature Analysis (`02_feature_analysis.py`) ✅ COMPLETE

Understand all 12 audio features and 6 genre columns to inform feature selection.

### 2a. Distribution plots
- Histogram + KDE for all 12 audio features (8 current + 4 dropped)

### 2b. Correlation matrix (12 audio + 6 genre cols)
- Confirmed: `energy` ↔ `loudness` strongly correlated (~0.75) — redundant
- Confirmed: `acousticness` strongly anti-correlated with `energy` (~-0.7) — independent signal
- Genre cols partially overlap with audio (rock↔energy, rap↔speechiness, etc.)

### 2c. Feature variance
- `mode` has artificially high variance (binary 0/1 → not informative, do not add)
- `key` has high variance but is categorical — not meaningful as continuous
- `loudness` has very low variance after MinMax scaling
- Genre cols have moderate variance (~0.13–0.15) from balanced class distribution

### 2d. PCA scree
- Audio-only (12 features): 7 PCs needed for 90% variance
- Audio + genre (w=0.3): 10 PCs needed — genre adds real but orthogonal signal

### Decisions from Phase 2
- **Feature space: audio only** — genre partially duplicates audio structure and
  compresses more audio information out of the 3D layout
- **Genre will be tested in Phase 4 ablation** to validate this decision empirically
- **Hypothesis to test in Phase 4**: swap `loudness` out, `acousticness` in
  (correlated pair, acousticness adds independent signal)
- `key`, `mode`, `duration_ms` remain dropped — categorical/low-signal

**Output:** `figures/02_feature_analysis/` — distributions, correlation heatmap,
variance bar chart, PCA scree plot

---

## Phase 3: Dimensionality Reduction Comparison (`03_reduction_comparison.py`) ✅ COMPLETE

Compare PCA, UMAP, t-SNE, and PaCMAP for producing a 3D space where sonic neighbors stay close.

**Input:** `features_minmax.npz` (8 features, MinMax-scaled, same input for all methods
so the comparison is fair). Ground-truth k-NN neighbors defined using cosine distance on
`features_unit.npz` (matches what the backend DB currently uses).

### Methods compared

| Method | Config | transform() support |
|---|---|---|
| PCA | n_components=3 | ✅ |
| UMAP | n_components=3, metric=cosine, n_neighbors=40, min_dist=0.4 | ✅ |
| t-SNE | n_components=3, perplexity=30, metric=cosine | ❌ |
| PaCMAP | n_components=3, n_neighbors=10, MN_ratio=0.5, FP_ratio=2.0 | ✅ |

### Quantitative metrics (per method)
- **Trustworthiness** (sklearn) — are 3D neighbors also high-D neighbors? (target > 0.85)
- **k-NN recall @ k=10** — fraction of true top-10 cosine neighbors recovered in 3D
- **Silhouette score by genre** — are same-genre songs clustered together?

### Results

| Method | Trustworthiness | k-NN Recall @10 | Silhouette | Time (s) |
|---|---|---|---|---|
| PCA | 0.887 | 0.142 | -0.070 | — |
| UMAP | 0.944 | 0.343 | -0.052 | — |
| t-SNE | 0.990 | 0.474 | -0.050 | — |
| PaCMAP | 0.934 | 0.251 | -0.068 | 7.1 |

### Decisions
- **t-SNE wins on metrics but is not viable** — no `transform()` for new points, breaks
  backend real-time user track projection.
- **UMAP is practical winner** — best trustworthiness (0.944) and k-NN recall (0.343)
  among `transform()`-capable methods. PaCMAP is faster (7s vs 27s) but lower recall.
- Phase 4 will run on UMAP with both audio-only and genre-included feature sets.

### Backend metric implications

| Winner | Implied DB metric change |
|---|---|
| UMAP (cosine) | None — keep cosine on unit vectors |
| PaCMAP | Keep cosine on unit vectors (PaCMAP uses euclidean internally but 3D layout quality is what matters) |
| PCA | Switch DB to euclidean on minmax-scaled vectors |
| t-SNE | ⚠️ No `transform()` — only viable if real-time user projection is dropped |

**Output:** `figures/03_reduction/` — scatter plots per method; `results/03_metrics.csv`
— numeric comparison table; winning method + DB metric recommendation carried into Phase 4+5

---

## Phase 4: Feature Set Ablation (`04_feature_ablation.py`)

Find the optimal feature subset using UMAP (winning method from Phase 3).
**All experiments run twice: once audio-only, once with genre one-hot at weight=0.3.**
This directly answers whether genre improves the layout across all configurations,
not just as a single add-on test.

### Approach

1. **Baseline A — audio only**: current 8 features → UMAP → trustworthiness + k-NN recall
2. **Baseline B — audio + genre**: 8 features + 6 genre cols (w=0.3) → UMAP → same metrics
   - Establishes whether genre helps or hurts before any feature changes
3. **Leave-one-out (audio-only)**: remove one audio feature at a time, re-run
   - Features that hurt metrics when removed are important; keep them
   - Features with flat delta are redundant; candidates for removal
4. **Targeted swaps from Phase 2 hypotheses** (audio-only):
   - Swap `loudness` → `acousticness` (correlated with energy; acousticness is independent)
   - Add `acousticness` without removing anything (9 features)
5. **Best audio-only subset** identified from steps 3–4
6. **Genre re-test on best subset**: apply genre cols (w=0.3) to the best audio-only subset
   - Final answer: does genre consistently improve or hurt?
7. **Best subset overall**: feature set (audio-only or +genre) with best metrics

### Output columns
`feature_set, genre_included, trustworthiness, knn_recall, silhouette`

**Output:** `results/04_ablation.csv`, `figures/04_ablation/` — bar charts comparing
audio-only vs genre-included side-by-side for each configuration

### Phase 4b: Genre Weight Sweep (`04b_genre_weight_sweep.py`) ✅ COMPLETE

Phase 4 showed genre hurts recall (0.343 → 0.230) but massively boosts silhouette
(−0.052 → 0.744). Since the UX goal is enjoyable neighbors — not just audio-optimal —
sweep genre weights to find the best recall/cluster tradeoff.

**Weights tested:** [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]

| Weight | Trustworthiness | k-NN Recall @10 | Silhouette |
|---|---|---|---|
| 0.00 | 0.9444 | 0.3429 | -0.052 |
| 0.05 | 0.9452 | 0.3473 | -0.050 |
| 0.10 | 0.9330 | 0.2577 | 0.144 |
| 0.20 | 0.9419 | 0.2297 | 0.594 |
| 0.30 | 0.9394 | 0.2298 | 0.744 |
| 0.50 | 0.9421 | 0.2288 | 0.744 |
| 0.70 | 0.9385 | 0.2201 | 0.700 |
| 1.00 | 0.9399 | 0.2224 | 0.772 |

**Decision: genre_weight = 0.1**
Chosen for subtle genre influence (sil=0.14, light clustering) while preserving
the most recall (0.258) among weights with any genre signal. Higher weights cause
aggressive genre segregation that overrides fine-grained audio similarity.

**Feature set going into Phase 5:** 8 audio features + genre one-hot × 0.1

**Output:**
- `results/04b_genre_weights.csv`
- `figures/04_ablation/genre_weight_metrics.png` — metrics vs weight line chart
- `figures/04_ablation/genre_weight_scatter.png` — point cloud grid per weight

---

## Phase 5: UMAP Hyperparameter Sweep (`05_sweep.py`)

Sweeps UMAP hyperparameters on the final feature set (8 audio + genre×0.1) to find
the best 3D layout. Winner from Phase 3 is UMAP.

**Feature set:** 8 audio features + genre one-hot × 0.1 (confirmed Phase 4b)
**Grid (60 configs):**
- `n_neighbors`: [10, 20, 40, 80]
- `min_dist`: [0.05, 0.1, 0.25, 0.4, 0.8]
- `metric`: [cosine, euclidean, correlation]

**Primary sort:** avg(trustworthiness, knn_recall)

Evaluate each combo with trustworthiness + k-NN recall.

**Output:** `results/05_sweep.csv`, heatmap of metric vs. primary hyperparameters

---

## Phase 6: Summary & Recommendations (`06_summary.md`) ✅ COMPLETE

---

## Phase 7: TriMAP Evaluation (`07_trimap_eval.py`) ✅ COMPLETE — KEEP UMAP

Test TriMAP as a drop-in replacement for UMAP. TriMAP explicitly optimises a triplet
ranking objective — anchor songs should be closer to near neighbors than to far ones —
which targets k-NN recall more directly than UMAP's fuzzy topological loss.

**Decision gate:** if TriMAP recall ≥ UMAP recall + 0.02 (≥ 0.287), adopt it in the
backend. Otherwise keep UMAP.

### Pipeline

```
data/features_minmax.npz  +  data/genres_onehot.npz
        ↓
concat(minmax_8, genre_onehot × 0.1)   shape (N, 14)
        ↓
TriMAP(n_dims=3, n_inliers=12, n_outliers=4, n_random=3)
        ↓
Normalize coords to [0, 1]³
        ↓
trustworthiness / k-NN recall @10 / silhouette
  (ground-truth k-NN: cosine on unit_8 — same as all prior phases)
        ↓
Compare to UMAP baseline (trust=0.954, recall=0.267, sil=0.221)
```

### Notes
- Feature set: 8 audio features + genre one-hot × 0.1 (identical to Phase 5 input)
- Ground-truth k-NN uses audio-only cosine on unit_8 — genre weight only shapes the
  embedding, not the definition of a "true" neighbor
- TriMAP supports out-of-sample extension via `trimap.transform()` (required for
  new-song projection at query time)
- **New dep:** `trimap`

**Output:** `results/07_trimap.csv`, scatter comparison vs. UMAP baseline

---

## Phase 8: Parametric UMAP (`08_parametric_umap.py`) ✅ COMPLETE — KEEP STANDARD UMAP

| | Fit time | transform() | Trust | Recall |
|---|---|---|---|---|
| Standard UMAP | 23.6s | 0.89 ms | 0.954 | 0.267 |
| Parametric UMAP | 3152s (~52 min) | 27 ms | 0.794 | 0.096 |

Parametric UMAP failed to converge (loss 0.25 → 0.31 across 10 epochs), collapsed recall
to 0.096 (vs 0.267), and is 3x slower at inference. Standard UMAP stays.

---

### Original proposal (for reference)

Replace `umap.UMAP` with `umap.ParametricUMAP`. Recall is equivalent to standard UMAP
but new-song projection becomes an exact neural forward pass rather than UMAP's
approximate `transform()`.

### Pipeline

**Fit (run once on full dataset):**
```
data/features_minmax.npz  +  data/genres_onehot.npz
        ↓
concat(minmax_8, genre_onehot × 0.1)   shape (N, 14)
        ↓
ParametricUMAP(n_components=3, metric="cosine",
               n_neighbors=40, min_dist=0.25)
        ↓
Save: encoder network weights  →  data/parametric_umap_encoder/
      full embedding matrix    →  data/parametric_umap_coords.npy
```

**New-song projection:**
```
8 audio features + genre one-hot × 0.1  →  concat (14D)
        ↓
MinMaxScaler.transform()   (scaler saved at fit time)
        ↓
encoder.predict(x)         (Keras forward pass, ~1 ms)
        ↓
3D coordinates
```

### Notes
- `umap.ParametricUMAP` requires a Keras backend (tensorflow or torch)
- Encoder saved as Keras SavedModel — loaded once at startup
- Fit time: ~5–10 min on CPU vs. ~17s for standard UMAP
- Validate by comparing embedding scatter vs. standard UMAP output
- **New dep:** `tensorflow` (or `torch` if already present)

**Output:** `data/parametric_umap_encoder/`, `results/08_parametric_umap_metrics.csv`,
scatter comparison vs. standard UMAP

---

## Phase 9: Local Scaling Post-Retrieval (`09_local_scaling.py`)

Apply Local Scaling to rerank similarity query results after k-NN search. No embedding
or feature changes — operates entirely on the retrieved candidate list.

Local Scaling normalises each pairwise distance by local density at both endpoints:

```
d'(x, y) = d(x, y) / (σ_x · σ_y)
```

where σ_x = distance from x to its 10th nearest neighbor (precomputed).

### Pipeline

**Precompute (run once):**
```
data/features_unit.npz
        ↓
NearestNeighbors(k=10, metric="cosine") on full dataset
        ↓
σ_i = distance to 10th neighbor for each song i
        ↓
data/local_scaling_sigmas.npy   (28k floats, ~220 KB)
```

**Evaluation (simulate recommendation queries):**
```
Hold out 500 query songs
        ↓
For each query: retrieve top 30 candidates by cosine on unit_8
        ↓
Rerank: d'(x, y) = d(x, y) / (σ_x · σ_y)
        ↓
Return top 10 reranked — measure k-NN recall @10
        ↓
Compare to baseline cosine retrieval (no reranking)
```

### Notes
- σ for unseen songs: compute on-the-fly against stored tracks (one extra k-NN call,
  cached after first use)
- If Local Scaling gains ≥ +0.03 recall, also test full Mutual Proximity as a
  stronger alternative
- No new deps

**Output:** `results/09_local_scaling_eval.csv` — recall comparison on held-out query set,
`data/local_scaling_sigmas.npy`

---

## Phase 10: FMA — Rich Audio Features POC (`10a`–`10c`)

**Goal:** Determine whether richer audio features break the recall ceiling (~0.267) using the
Free Music Archive (FMA) dataset as a controlled testbed.

**Why FMA:** Spotify `preview_url` is deprecated and blocked under development-mode API access.
FMA ships with both Echonest-style sparse features and pre-extracted librosa features on the
same tracks, enabling a clean controlled experiment.

**Controlled experiment design:**

| Run | Features | Dims | Purpose |
|-----|----------|------|---------|
| A — FMA sparse | Echonest features (danceability, energy, tempo, valence, …) | ~8D | FMA baseline — Spotify-equivalent |
| B — FMA rich   | Pre-extracted librosa (MFCC, chroma, spectral contrast, …)  | ~518D → PCA 32D | Tests rich feature hypothesis |

If B recall > A recall on the same dataset, the improvement is attributable to richer
features — not dataset quality. This validates the approach before investing in audio
extraction on the Spotify catalog.

**Dataset:** `fma_medium` — 25,000 tracks, 30s clips, 16 top-level genres, ~8GB audio.
Pre-extracted features ship separately as CSVs (~50MB). Audio not needed for this phase.

**Decision gate:** if (B recall − A recall) ≥ +0.05 → richer features are load-bearing →
proceed to Phase 11. Otherwise the feature ceiling is fundamental, not data-dependent.

---

### 10a — Download + Inspect FMA Features (`10a_fma_setup.py`)

```
Download (if not present):
  fma_metadata.zip  →  data/fma_metadata/
    ├── echonest.csv   (sparse, Spotify-equivalent features)
    ├── features.csv   (pre-extracted librosa features, ~518D)
    ├── tracks.csv     (metadata: title, artist, genre, split)
    └── genres.csv     (genre taxonomy)

Inspect:
  - Track count per top-level genre
  - Echonest feature columns available
  - Librosa feature shape
  - Missing value counts
```

**Output:** `data/fma_metadata/` directory, printed summary.
**Source:** https://github.com/mdeff/fma (metadata zip, not audio)

---

### 10b — Run A: FMA Sparse Baseline (`10b_fma_sparse.py`)

```
echonest.csv  →  select Spotify-equivalent columns
                 (danceability, energy, tempo, valence,
                  acousticness, instrumentalness, liveness, speechiness)
        ↓
Drop rows with any NaN  →  N_sparse tracks
        ↓
MinMaxScaler  →  L2 normalize  (mirrors Phase 1–5 pipeline exactly)
        ↓
UMAP (cosine, n_neighbors=40, min_dist=0.25)  →  3D coords
        ↓
Metrics (ground truth = cosine on scaled sparse features):
  - trustworthiness @10
  - k-NN recall @10
  - silhouette by genre (subsample 3000)
```

**Output:** `results/10b_fma_sparse.csv`, `figures/10b_sparse_scatter.png`

---

### 10c — Run B: FMA Rich Features (`10c_fma_rich.py`)

```
features.csv  →  ~518D pre-extracted librosa features
                 (MFCC ×7 stats, chroma, spectral, tonnetz, ZCR, …)
        ↓
Align to same track IDs as Run A  →  N_shared tracks
        ↓
StandardScaler (z-score — features span very different ranges)
        ↓
PCA → 32D  (scree plot saved, retain ~95% variance)
        ↓
UMAP (cosine, n_neighbors=40, min_dist=0.25)  →  3D coords
        ↓
Metrics (ground truth = cosine on 32D PCA features):
  - trustworthiness @10
  - k-NN recall @10
  - silhouette by genre (subsample 3000)
        ↓
Direct comparison table vs Run A
```

**Output:** `results/10c_fma_rich.csv`, `figures/10c_rich_scatter.png`,
`figures/10c_pca_scree.png`, `results/10_comparison.csv`

---

### Notes
- Only `fma_metadata.zip` needed (~50MB) — no audio download required for this phase.
- Track alignment: both runs use the intersection of tracks present in echonest.csv AND
  features.csv to ensure fair comparison on identical track sets.
- If rich features win: Phase 11 will extract the same librosa features from Spotify
  previews (via Deezer API as preview source) for the production Spotify catalog.
- Feature ablation (drop-one-group) deferred to Phase 11 once approach is validated.

Auto-generated markdown document that:
1. States the winning reduction method and why (metric table from Phase 3)
2. States the final recommended feature set and why (ablation results from Phase 4)
3. States the optimal hyperparameters (sweep results from Phase 5)
4. Lists expected metric values (trustworthiness, k-NN recall, silhouette)
5. Notes any caveats or next steps

---

## Directory Layout

```
analysis/
├── PLAN.md                   ← this file
├── 01_ingest.py
├── 02_feature_analysis.py
├── 03_reduction_comparison.py
├── 04_feature_ablation.py
├── 05_umap_sweep.py
├── 06_summary.md
├── data/                     ← cached numpy arrays (gitignored, regenerate from CSV)
│   ├── features_raw.npz
│   ├── features_minmax.npz
│   ├── features_unit.npz
│   ├── genres_onehot.npz
│   └── metadata.csv
├── figures/                  ← saved plots (gitignored)
│   ├── 02_feature_analysis/
│   ├── 03_reduction/
│   ├── 04_ablation/
│   └── 05_sweep/
└── results/                  ← metrics CSVs (checked in)
    ├── 03_metrics.csv
    ├── 04_ablation.csv
    ├── 05_sweep.csv
    └── 06_summary.md
```

---

## Dependencies (add to a `requirements.txt` in analysis/)

```
pandas
numpy
scikit-learn
umap-learn
matplotlib
seaborn
joblib
jupyter
```

All already available in the backend `.venv` except `seaborn`.
