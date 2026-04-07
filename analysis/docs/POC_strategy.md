# POC Strategy: Improving Recall via Richer Audio Features

## Problem

Current system: 8D Spotify metadata features → UMAP 3D.
Recall ceiling: **~0.267 @10** (Phase 5 sweep, 60 configs tested).

This ceiling is not a dimensionality reduction problem — all DR methods and hyperparameters were exhausted (Phases 3, 5, 7, 8). Post-retrieval reranking also provides no benefit (Phase 9). The bottleneck is **feature quality**: Spotify's 8 features are high-level metadata that don't encode timbre, texture, or fine-grained audio structure.

---

## Root Cause

| Feature          | What it captures        | What it misses                  |
|------------------|-------------------------|---------------------------------|
| danceability     | rhythmic regularity     | specific drum patterns, groove  |
| energy           | overall intensity       | timbral texture, dynamics       |
| valence          | emotional positivity    | modal color, harmonic tension   |
| tempo            | BPM                     | rhythmic complexity, syncopation|
| instrumentalness | vocal presence          | instrument timbre, arrangement  |
| …                | …                       | …                               |

Two songs can share all 8 feature values yet sound completely different. The neighborhood structure is genuinely noisy in 8D.

---

## Strategy: Two-Phase Feature Upgrade

### Phase A — Librosa Feature Extraction (POC, no DL model)

**Goal:** Expand from 8D to ~60–80D using classical signal processing on 30s previews.
**Expected recall:** 0.35–0.45 (estimated).

**Why start here:**
- No heavy model setup or GPU required
- librosa is already in the Python ecosystem
- Produces interpretable, music-specific features
- Directly comparable to current pipeline (same UMAP + evaluation harness)

**Features to extract per track:**

| Feature Group     | Dimensionality | Captures                          |
|-------------------|---------------|-----------------------------------|
| MFCC (mean+std)   | 26D           | Timbre, vocal/instrument texture  |
| Chroma (mean+std) | 24D           | Harmonic content, key, chord feel |
| Spectral contrast | 14D           | Brightness, bass/treble balance   |
| Tempo + beat      | 2D            | Rhythmic structure                |
| Zero crossing rate| 2D            | Noisiness, percussiveness         |

Combined: ~68D raw → **32D after PCA** → UMAP 3D.

**Data dependency:** Spotify preview URLs (`preview_url` field from API). ~15–20% of tracks may return null — those fall back to existing 8D features.

---

### Phase B — Deep Audio Embeddings (if Phase A validates approach)

**Goal:** Replace librosa features with a pretrained audio neural network, targeting 0.45–0.60 recall.

**Recommended model: PANNs CNN14**
- Pretrained on AudioSet (2M+ clips, 527 classes)
- Outputs 2048D embedding from global average pool
- Strong general-purpose audio representation proven in MIR research
- Available via `panns-inference` pip package

**Alternative: CLAP (Microsoft)**
- Contrastive Language-Audio Pretraining, 512D
- Music-aware (trained on music + audio + text)
- Enables future text-to-audio search ("find me something chill and jazzy")
- Available via `msclap` pip package

**Pipeline:**

```
30s MP3 preview  →  resample to 22050 Hz
        ↓
PANNs CNN14 forward pass
        ↓
2048D embedding (per track)
        ↓
PCA → 32D  (noise reduction, stabilises DR)
        ↓
UMAP (cosine, n_neighbors=40, min_dist=0.25)  →  3D coords
```

---

## What We Are NOT Doing (and Why)

| Rejected approach       | Reason                                                   |
|-------------------------|----------------------------------------------------------|
| PaCMAP as primary DR    | Phase 3: recall=0.251 vs UMAP=0.343 — UMAP wins         |
| TriMAP                  | Phase 7: recall=0.180, 34% below UMAP                   |
| Parametric UMAP         | Phase 8: recall=0.096, non-convergent, 52min fit         |
| Local Scaling / MP post-rerank | Phase 9: Δ=-0.003 — UMAP output has uniform local density, no benefit |
| Adding acousticness     | Phase 4: hurts recall (0.343→0.228)                      |

---

## Evaluation Plan

Same harness as Phases 3–9:
- **Ground truth:** cosine k-NN on raw high-D embeddings (the new features replace unit_8)
- **Metrics:** trustworthiness @10, k-NN recall @10, silhouette by genre
- **Baseline to beat:** trust=0.954, recall=0.267, sil=0.221

A new `10_audio_features.py` script should:
1. Load preview URLs from `spotify_songs.csv`
2. Download previews (async, with retries and null handling)
3. Extract librosa features, save to `data/librosa_features.npz`
4. Run the standard UMAP config and compute all three metrics
5. Report direct comparison vs Phase 5 winner

---

## Success Criteria

| Milestone                    | Target recall @10 |
|------------------------------|-------------------|
| Phase A (librosa, 68D→32D→3D)| ≥ 0.35            |
| Phase B (PANNs, 2048D→32D→3D)| ≥ 0.45            |
| Acceptable for production    | ≥ 0.40            |

If Phase A recall < 0.30, it suggests preview audio quality or coverage is too poor to help, and Phase B should be attempted directly with a larger model.
