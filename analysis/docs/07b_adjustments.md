# Improving 3D Song Similarity for the Music Map

## Overview

The current system uses:

- **8D cosine similarity** for determining song similarity
- **3D UMAP** for visualization in the point cloud

However, this leads to a common issue:

Many songs that are considered neighbors in the 8D space appear **far away in the 3D visualization**.

This occurs because dimensionality reduction can distort local neighborhood relationships. The goal of this document is to evaluate possible improvements and propose a revised roadmap based on research in:

- Music Information Retrieval (MIR)
- Dimensionality reduction
- Similarity search
- Neighbor preservation

The objective is to **increase KNN recall in the 3D space**, so that visually nearby songs correspond more closely to similarity neighbors.

---

# Overall Assessment

The proposal correctly identifies three major areas that influence the quality of a 3D music similarity map:

1. Distance metric improvements (hubness reduction, Mutual Proximity)
2. Better dimensionality reduction objectives (parametric models or neural methods)
3. Improved feature representations (deep audio embeddings)

These areas align well with the literature on music similarity and manifold learning.

However, several adjustments are recommended:

- The **priority ordering should change**
- The **Mutual Proximity implementation approach should be corrected**
- **Autoencoder-based dimensionality reduction is likely unnecessary** given the current feature dimensionality
- Alternative DR methods designed for **neighbor preservation** should be tested

---

# Mutual Proximity (MP)

## Current Proposal

The proposal suggests:

8D cosine distances → Mutual Proximity → feed into UMAP

However, this is **not how Mutual Proximity is typically used**.

Mutual Proximity transforms **neighbor relationships**, not static distance matrices.

The formulation is:

MP(x,y) = 1 - P(d_x > d(x,y)) * P(d_y > d(x,y))

This converts distances into probabilities relative to each point's distance distribution.

In research systems (e.g., Musly, ISMIR similarity search papers), MP is used **during neighbor retrieval**, not during dimensionality reduction.

---

## Problem with Feeding MP Distances to UMAP

UMAP assumes the input distances behave like a metric space.

Mutual Proximity distances are **not metric**, which can produce:

- unstable embeddings
- distorted manifold structure

---

## Correct Implementation Strategy

Use MP **after dimensionality reduction** when retrieving neighbors.

Recommended pipeline:

8D feature vectors  
↓  
UMAP → 3D embedding  
↓  
KNN search  
↓  
Mutual Proximity reweighting

This approach preserves the integrity of the embedding while improving neighbor ranking.

---

# Parametric UMAP

Parametric UMAP replaces the nonparametric embedding with a neural network that learns the mapping.

Benefits:

- Faster inference
- Stable projections for new songs
- Ability to embed new tracks without recomputing the entire layout

Example architecture:

8D features → neural network → 3D embedding

---

## Recommendation

Parametric UMAP should be considered **a high-priority improvement** because it:

- improves scalability
- stabilizes the embedding
- simplifies adding new tracks

---

# Regularized Autoencoder (RAE)

Regularized autoencoders were proposed as a potential dimensionality reduction technique.

However, this approach is likely **unnecessary for the current feature space**.

Current input dimensionality:

~8 Spotify audio features (+ possible genre features) ≈ 8–14 dimensions

Autoencoders typically provide the most benefit when reducing **very high-dimensional inputs**, such as:

512 → 3  
768 → 2  
2048 → 3

Reducing **8D → 3D** is already a small transformation, meaning neural DR methods provide limited advantage.

UMAP already performs very well in this dimensionality range.

---

## Recommendation

Do **not prioritize autoencoder approaches yet**.

Instead, test dimensionality reduction algorithms specifically designed to preserve neighbor structure.

Recommended methods to test:

- PaCMAP
- TriMAP
- LargeVis
- UMAP

Among these, **PaCMAP** is especially strong for preserving local neighborhoods.

---

# Feature Representation Limitations

The current feature set uses Spotify audio descriptors such as:

danceability  
energy  
valence  
loudness  
tempo  
acousticness  
instrumentalness  
speechiness

These are useful but **very coarse representations** of music.

They capture high-level attributes but miss important signals for perceptual similarity such as:

- timbre
- instrumentation
- production style
- harmonic content

Music similarity research consistently finds that **audio embeddings outperform metadata features**.

Common representations include:

- MFCC features
- MusiCNN embeddings
- PANN embeddings
- VGGish audio embeddings
- CLAP embeddings

---

## Recommended Feature Pipeline

audio preview  
↓  
deep audio embedding (128–512D)  
↓  
UMAP / PaCMAP → 3D

This approach significantly improves clustering and neighborhood preservation.

---

# Additional Technique: Local Scaling

A simple but powerful technique used in similarity search is **Local Scaling**.

Distance is normalized relative to local density:

d'(x,y) = d(x,y) / (σ_x σ_y)

This helps prevent dense regions from dominating the similarity structure and often improves neighbor consistency.

Local Scaling is much simpler than Mutual Proximity and can be applied during similarity computation.

---

# Recommended Priority Order

### Priority 1 — Test Neighbor-Preserving DR

Evaluate:

PaCMAP  
TriMAP  
UMAP  

Expected improvement: **+5–15% KNN recall**

---

### Priority 2 — Switch to Parametric UMAP

Benefits:

- fast new-song projection
- stable embeddings
- scalable system

---

### Priority 3 — Apply Mutual Proximity to Similarity Queries

Use MP **during neighbor ranking**, not embedding generation.

Expected improvement: **+5–10% recall**

---

### Priority 4 — Expand Feature Set

Add richer acoustic descriptors such as:

- MFCC features
- spectral features

Even adding ~20 MFCC features may improve structure.

---

### Priority 5 — Deep Audio Embeddings

Long-term improvement:

audio preview  
↓  
MusiCNN / PANN embedding (256D)  
↓  
PCA → 32D  
↓  
PaCMAP → 3D

This pipeline is commonly used in modern music similarity systems.

---

# Final Verdict

The proposal is **well researched and directionally correct**, but the implementation roadmap should be adjusted.

Key corrections:

- Do **not feed Mutual Proximity into UMAP**
- **Prioritize PaCMAP/TriMAP testing**
- **Deprioritize autoencoders for now**
- **Strongly consider richer audio representations**

The biggest improvements will likely come from:

1. Better dimensionality reduction objectives
2. Improved feature representations
3. Post-processing similarity metrics such as Mutual Proximity or Local Scaling