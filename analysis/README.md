# Music Similarity Analysis

Research pipeline for determining the best features and dimensionality reduction method to build a 3D sonic similarity space where proximity = musical similarity.

All scripts are run from the `analysis/` directory. Data and results are written to `data/` and `results/`.

---

## Directory Layout

```
analysis/
├── scripts/
│   ├── spotify_8d/     # Phase 1 — Spotify 8D feature pipeline (scripts 01–09)
│   └── fma_rich/       # Phase 2 — FMA rich audio features (scripts 10a–10c)
├── data/               # Generated data files (.npz, .npy, .parquet, .csv)
├── results/            # Metric outputs (.csv)
├── figures/            # Generated plots (.png)
├── docs/               # Research documents, reports, proposals
├── PLAN.md             # Master plan — phase specs, pipelines, decision gates
└── README.md
```

---

## Phase 1 — Spotify 8D Features (`scripts/spotify_8d/`)

Starting point: 28,356 tracks with 8 Spotify audio features (danceability, energy, loudness, speechiness, instrumentalness, liveness, valence, tempo).

**Goal:** Find the best DR method and feature set for a 3D similarity space.

| Script | What it does |
|--------|-------------|
| `01_ingest.py` | Load and clean `spotify_songs.csv`, produce `data/features_*.npz` |
| `02_feature_analysis.py` | EDA — distributions, correlations, PCA variance |
| `03_reduction_comparison.py` | Compare UMAP vs PCA vs t-SNE vs PaCMAP on 8D features |
| `04_feature_ablation.py` | Leave-one-out ablation — which audio features matter most |
| `04b_genre_weight_sweep.py` | Sweep genre one-hot weight (0.0–1.0), pick w=0.1 |
| `05_sweep.py` | 60-config UMAP hyperparameter grid (metric × n_neighbors × min_dist) |
| `05b_top5_scatter.py` | Point cloud scatter for top 5 UMAP configs |
| `07_trimap_eval.py` | TriMAP evaluation vs UMAP winner |
| `08_parametric_umap.py` | Parametric UMAP (neural encoder) evaluation |
| `09_local_scaling.py` | Post-retrieval Local Scaling reranking on 3D UMAP coords |

### Key Results

| Metric | Value |
|--------|-------|
| Winner method | UMAP (cosine, n_neighbors=40, min_dist=0.25) |
| Trustworthiness @10 | 0.954 |
| k-NN Recall @10 | 0.267 |
| Feature set | 8 Spotify audio features + genre one-hot × 0.1 |
| Recall ceiling | ~0.267 — all DR methods, hyperparameters, and post-retrieval reranking exhausted |

**Conclusion:** The recall ceiling is a feature quality problem, not a DR problem. Spotify's 8 metadata features do not capture timbre or fine-grained audio structure. See [`docs/POC_strategy.md`](docs/POC_strategy.md) for the full diagnosis.

**Detailed results:** [`results/05_sweep.csv`](results/05_sweep.csv) | [`docs/SUMMARY.md`](docs/SUMMARY.md)

---

## Phase 2 — FMA Rich Audio Features (`scripts/fma_rich/`)

Testing whether richer audio features (518D librosa features from the FMA dataset) break the recall ceiling established in Phase 1.

**Dataset:** [Free Music Archive (FMA)](https://github.com/mdeff/fma) — 49,598 tracks with pre-extracted librosa features (MFCCs, chroma, spectral contrast, tonnetz, ZCR, etc.) and genre labels.

**Why FMA:** Provides both high-level Echonest/Spotify-like features and full librosa features for the same tracks, enabling controlled comparison. Audio files not required — features are pre-computed.

| Script | What it does |
|--------|-------------|
| `10a_fma_setup.py` | Download FMA metadata (~50MB), extract, inspect coverage, save `data/fma_tracks.parquet` |
| `10b_fma_eval.py` | 518D → PCA 213D (95% variance) → UMAP 3D, compute recall vs Phase 1 baseline |
| `10c_tsne.py` | Same pipeline with t-SNE instead of UMAP |

### Key Results

| Method | Recall @10 | Trustworthiness | Fit time |
|--------|-----------|----------------|---------|
| UMAP (Phase 1 baseline, Spotify 8D) | 0.267 | 0.954 | 23.6s |
| UMAP (FMA 518D → PCA 213D) | 0.062 | 0.869 | 46.7s |
| **t-SNE (FMA 518D → PCA 213D)** | **0.274** | **0.928** | 403s |

**Finding:** t-SNE on rich 518D features matches Phase 1 recall (0.274 vs 0.267) where UMAP completely fails. This confirms that richer audio features *do* contain better neighborhood structure — t-SNE's affinity matrix can find it, but UMAP's approximate k-NN graph construction breaks down at 213D input.

**Next step:** Phase 11 — deep audio embeddings (PANNs / CLAP) targeting recall ≥ 0.45. See [`PLAN.md`](PLAN.md) for the full roadmap.

---

## Running Scripts

```bash
# From the analysis/ directory, with the venv activated:
source ../backend/.venv/bin/activate

# Phase 1 (run in order)
python3 scripts/spotify_8d/01_ingest.py
python3 scripts/spotify_8d/02_feature_analysis.py
# ... etc

# Phase 2
python3 scripts/fma_rich/10a_fma_setup.py   # downloads FMA metadata
python3 scripts/fma_rich/10b_fma_eval.py
python3 scripts/fma_rich/10c_tsne.py
```

---

## Research Documents (`docs/`)

| Document | Contents |
|----------|---------|
| [`SUMMARY.md`](docs/SUMMARY.md) | Concise summary of Phase 1 results and metrics |
| [`POC_strategy.md`](docs/POC_strategy.md) | Diagnosis of recall ceiling + Phase 2 strategy |
| [`embedding_improvement_proposal.md`](docs/embedding_improvement_proposal.md) | Proposal for deep audio embeddings (PANNs, CLAP) |
| [`deep-research-report.md`](docs/deep-research-report.md) | Agent-researched survey of advanced DR and similarity methods |
| [`07_synthesis.md`](docs/07_synthesis.md) | Synthesis of research findings and method proposals |
| [`07b_adjustments.md`](docs/07b_adjustments.md) | Revised proposals after reviewing research report |
| [`06_summary.md`](docs/06_summary.md) | Auto-generated Phase 1 summary document |
