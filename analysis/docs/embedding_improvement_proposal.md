
# Proposal: Embedding Improvements for 3D Music Similarity

## 1. Problem Summary

The current system uses:

- **8D Spotify audio features** for similarity (cosine distance)
- **3D UMAP** for visualization

Observed issue:

> Songs that are neighbors in 8D space often appear far apart in the 3D point cloud.

This indicates **low KNN recall after dimensionality reduction**, limiting the usefulness of the visualization.

---

## 2. Core Limitation

The main bottleneck is not just dimensionality reduction, but **feature quality**.

Spotify features:
- are low-dimensional (~8D)
- capture high-level attributes
- do NOT encode timbre or detailed audio structure

Result:
- weak separation between songs
- unstable neighborhoods
- poor preservation in 3D

---

## 3. Proposal Overview

We propose replacing the current feature pipeline with **learned audio embeddings (128D+)**, followed by optimized dimensionality reduction.

### New Pipeline

Spotify Track  
↓  
30s audio preview  
↓  
Audio Embedding Model (PANNs / MusiCNN)  
↓  
128–512D embedding  
↓  
PCA → 32D  
↓  
PaCMAP (or UMAP) → 3D  

---

## 4. Embedding Sources

### Option 1 — PANNs (Recommended)

- Pretrained on AudioSet
- Outputs 128–2048D embeddings
- Strong general-purpose audio representation

**Why use:**
- Best balance of quality and accessibility
- Proven performance in MIR research

---

### Option 2 — MusiCNN

- Trained specifically on music
- ~128–256D embeddings

**Why use:**
- Better genre/style modeling
- More music-focused than PANNs

---

### Option 3 — VGGish

- 128D embeddings
- Lightweight and fast

**Tradeoff:**
- Slightly weaker representation

---

## 5. Dimensionality Reduction Strategy

### Step 1: PCA (128D → 32D)

- removes noise
- stabilizes DR
- improves performance

---

### Step 2: DR Method Comparison

Test:

- **PaCMAP (priority)**
- UMAP
- TriMAP

**Why PaCMAP:**
- optimized for local neighbor preservation
- typically improves KNN recall

---

## 6. Similarity Improvements

### Mutual Proximity (MP)

Apply AFTER embedding for neighbor ranking:

3D embedding  
↓  
KNN search  
↓  
MP reweighting  

Improves recall without distorting embedding.

---

### Local Scaling (Alternative)

Normalize distances using local density:

d'(x,y) = d(x,y) / (σ_x σ_y)

Simpler and often effective.

---

## 7. Implementation Plan

### Phase 1 — Embedding Extraction

- Use PANNs model
- Extract embeddings for all songs
- Store as vectors

---

### Phase 2 — DR Evaluation

- Run PaCMAP, UMAP, TriMAP
- Compute:
  - recall@k
  - visual clustering

---

### Phase 3 — Integration

- Replace 8D features with embeddings
- Update visualization pipeline
- Maintain cosine similarity in high-D space

---

### Phase 4 — Optimization

- Tune DR parameters
- Add PCA preprocessing
- Experiment with MP / Local Scaling

---

## 8. Evaluation Metrics

Track:

### KNN Recall@k

Compare:

high-D neighbors vs 3D neighbors

---

### Trustworthiness

Measures local structure preservation

---

### Visual Quality

- cluster coherence
- genre grouping
- separation

---

## 9. Expected Improvements

Current:

- ~25% recall (8D → 3D)

With embeddings:

- **40–60% recall (expected)**

Also:

- tighter clusters
- more intuitive layout
- fewer scattered neighbors

---

## 10. Risks

### Compute

- embedding extraction cost
- mitigated via offline processing

---

### Data Dependency

- requires audio previews

---

### Remaining Distortion

- 3D will always be lossy
- but significantly improved

---

## 11. Final Recommendation

Adopt the following pipeline:

PANNs embeddings (128–512D)  
↓  
PCA → 32D  
↓  
PaCMAP → 3D  

With:

- MP or Local Scaling for similarity refinement

---

## 12. Next Steps

1. Implement embedding extraction
2. Benchmark vs current system
3. Select best DR method
4. Deploy updated visualization

---

This proposal targets the root cause of low recall: **insufficient feature representation**, not just dimensionality reduction.
