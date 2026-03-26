# Research Synthesis & Next Steps

Synthesizes `deep-research-report.md` and `07b_adjustments.md` against the current
Soundgaze pipeline (`06_summary.md`). Where the two sources disagreed, reasoning is
provided for the decision taken.

---

## Current Pipeline State

| Stage | Current approach | Metric |
|---|---|---|
| Features | 8 Spotify audio features + genre one-hot × 0.1 | — |
| Reduction | UMAP cosine, n_neighbors=40, min_dist=0.25 | trust=0.954, recall=0.267 |
| DB similarity | Cosine on 8D L2-normalised audio vectors | — |
| New-point projection | `umap.transform()` at query time | — |

Primary weakness: **k-NN recall @10 = 0.267** — roughly 1 in 4 true audio neighbors
appear in a song's 3D neighborhood. The 8D→3D compression sets a hard ceiling but
meaningful headroom remains.

---

## Where the Two Research Sources Disagreed — Decisions Taken

### Mutual Proximity: pre- vs. post-UMAP

**Original proposal (07_synthesis):** apply MP to the 8D distance matrix and feed
the result into UMAP as a precomputed metric.

**Adjustment (07b):** this is incorrect. MP produces non-metric distances (it converts
raw distances to probabilities). UMAP assumes a valid metric space; feeding MP distances
in can produce unstable embeddings and distorted manifold structure.

**Decision: accept the correction.** MP belongs after UMAP — applied to 3D neighbor
rankings at query time, not during embedding. The corrected pipeline is:

```
8D features → UMAP → 3D embedding → k-NN search → MP/Local Scaling reranking
```

---

### Regularized Autoencoder (RAE): keep vs. drop

**Original proposal:** train a 3-layer MLP with a k-NN preservation loss as the
primary recall improvement.

**Adjustment:** autoencoders add most value reducing very high-dimensional inputs
(512D→3D, 2048D→3D). At 8D→3D UMAP is already competitive; the neural overhead
is not justified.

**Decision: partially accept — deprioritize, not drop.** The adjustment is correct
that the dimensionality argument weakens the RAE case. However, RAE's advantage is
the explicit k-NN loss, not dimensionality handling alone. That said, TriMAP encodes
the same neighbor-preserving objective (via triplet ranking) without requiring a neural
training loop, and it is untested. TriMAP should be evaluated before committing to RAE.
If TriMAP fails to improve on UMAP, RAE becomes worth revisiting.

---

### PaCMAP: recommended vs. already tested

**Adjustment:** recommends PaCMAP as "especially strong for preserving local neighborhoods."

**Our Phase 3 data:** PaCMAP recall = 0.251 vs. UMAP recall = 0.343 (audio-only, same
input). With genre × 0.1, UMAP recall = 0.267. PaCMAP was worse than UMAP in our
specific feature space. The adjustment's general recommendation does not hold here.

**Decision:** PaCMAP is already ruled out by our own empirical results. TriMAP is the
untested neighbor-preserving DR method worth evaluating next.

---

## Revised Next Steps — Prioritised

### Priority 1 — Test TriMAP as DR alternative (low-medium effort)

TriMAP explicitly optimises a triplet-based objective: anchor songs should be closer
to near neighbors than to far ones. This is conceptually the neighbor-preserving loss
that motivated RAE, but implemented as a DR algorithm rather than a neural network —
no training loop, no additional dependencies beyond `trimap` package.

Our Phase 3 showed UMAP > PaCMAP for recall. TriMAP is the next untested candidate
that directly targets local neighbor preservation and also supports `transform()`.

```
analysis/08_trimap_eval.py
  - Same setup as 03_reduction_comparison.py
  - Compare TriMAP vs. UMAP (cosine, n_neighbors=40, min_dist=0.25) + genre×0.1
  - Metrics: trustworthiness, k-NN recall @10, silhouette
  - If TriMAP recall ≥ UMAP + 0.02: adopt it in mapping.py
```

**Expected gain (per literature):** +5–15% k-NN recall. Our Phase 3 data suggests
our feature space is harder than average, so temper expectations.

---

### Priority 2 — Parametric UMAP (low effort, stabilises new-point projection)

Both research sources agree this is high priority. Replaces `umap.transform()`
(an approximation) with a learned neural encoder that is an exact function of the input.
Recall is equivalent to standard UMAP; the benefit is projection stability for new songs.

Available in `umap-learn` with no new dependencies:

```python
# backend/mapping.py
from umap.parametric_umap import ParametricUMAP
reducer = ParametricUMAP(
    n_components=3, metric="cosine",
    n_neighbors=40, min_dist=0.25,
)
```

Fit time increases (~5–10 min on CPU vs. ~17s), but the saved encoder makes subsequent
`transform()` calls exact forward passes. No schema or frontend changes required.

---

### Priority 3 — Mutual Proximity / Local Scaling on similarity queries (low effort)

Apply MP or Local Scaling **after** the 3D k-NN search during `/songs/recommend` and
random-walk queries. This reranks the retrieved neighbor list without touching the
embedding or DB schema.

**Local Scaling** (simpler, recommended to try first):

```python
# d'(x, y) = d(x, y) / (sigma_x * sigma_y)
# sigma_x = distance from x to its k-th neighbor
```

**Mutual Proximity** (stronger, more complex):

```
MP(x,y) = 1 - P(d_x > d(x,y)) * P(d_y > d(x,y))
```

Both operate on the retrieved candidate list, not the full distance matrix, so
they are O(k) per query. Estimated gain: +5–10% recall on returned neighbor lists.

Implementation lives in `backend/similarity.py` or inline in the recommendation
endpoint — no model retraining needed.

---

### Priority 4 — MFCC / Spectral features from Spotify preview URLs (medium effort)

Both sources agree richer features are the highest-ceiling improvement. Spotify exposes
30-second MP3 previews for most tracks via the API (`preview_url` field). Extracting
~20 MFCC coefficients per track using `librosa` would add timbre and production-style
signals that the current 8 features entirely miss.

```
Spotify preview URL → librosa MFCC extraction → 20D timbre vector
Concatenate with 8D audio features → 28D input to UMAP/TriMAP
```

This requires a one-time batch job during ingest (`backend/ingest.py`) and does not
change the DB schema if the MFCC features are baked into the unit vector before storage.

**Caveat:** ~10–15% of tracks have no preview URL and would require a fallback
(zero-fill or imputation).

---

### Priority 5 — Deep audio embeddings: MusiCNN / PANNs / CLAP (high effort)

Long-term step-change improvement. Replace the 8D feature vector entirely with a
pretrained deep audio embedding (128–512D) extracted from the 30s preview:

```
audio preview → MusiCNN / PANNs / CLAP → 256D embedding
→ PCA → 32D → TriMAP/UMAP → 3D
```

Music similarity research consistently finds deep embeddings produce far tighter
and more perceptually meaningful neighbor clusters than metadata features.

This is a full pipeline rebuild: new ingest, new DB collection, full re-evaluation
of all Phase 3–5 analysis on the new feature space. Treat as a separate roadmap
milestone once the current pipeline is production-stable.

---

## Revised Summary Table

| Next step | Effort | Expected recall gain | Correctness risk |
|---|---|---|---|
| TriMAP evaluation | Low | +5–15% (uncertain) | Low |
| Parametric UMAP | Low | ~0 (stability gain) | Low |
| MP / Local Scaling post-retrieval | Low | +5–10% on returned lists | Low |
| MFCC features from preview URLs | Medium | Moderate (est. +5–15%) | Medium |
| RAE (if TriMAP fails) | Medium | +5–15% (uncertain) | Medium |
| Deep audio embeddings | High | Large (step-change) | High |

**Recommended execution order:**
TriMAP eval → Parametric UMAP → Local Scaling post-retrieval → MFCC features.
Deep embeddings and RAE are longer-horizon work.

---

## What Was Rejected and Why

| Proposal | Source | Rejection reason |
|---|---|---|
| MP as UMAP precomputed metric | 07_synthesis | MP distances are non-metric; violates UMAP assumptions |
| RAE as Priority 3 | 07_synthesis | Overkill for 8D→3D; TriMAP tests the same hypothesis more cheaply |
| PaCMAP as priority DR candidate | 07b_adjustments | Already empirically worse than UMAP in Phase 3 (recall 0.251 vs 0.267) |
