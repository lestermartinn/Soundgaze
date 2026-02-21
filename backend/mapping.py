"""
Mapping module — placeholder for UMAP dimensionality reduction.

Reduces 12-D Spotify audio feature vectors to 3-D (x, y, z) coordinates
suitable for rendering in the Three.js point cloud.

Install: pip install umap-learn
"""

from __future__ import annotations

from models import AudioFeatures, EmbeddedPoint


def reduce_to_3d(tracks: list[AudioFeatures]) -> list[EmbeddedPoint]:
    """
    Project a list of tracks from 12-D audio-feature space to 3-D via UMAP.

    Args:
        tracks: List of AudioFeatures objects (one per song).

    Returns:
        List of EmbeddedPoint with (x, y, z) coordinates.

    TODO: Uncomment the real UMAP block below and remove the random fallback.
    """

    # ------------------------------------------------------------------
    # REAL UMAP IMPLEMENTATION (uncomment when umap-learn is installed)
    # ------------------------------------------------------------------
    # import numpy as np
    # import umap
    #
    # vectors = np.array([t.to_vector() for t in tracks], dtype=np.float32)
    #
    # reducer = umap.UMAP(
    #     n_components=3,
    #     n_neighbors=15,       # balance local vs. global structure
    #     min_dist=0.1,         # tightness of clusters
    #     metric="cosine",      # matches our similarity metric
    #     random_state=42,
    # )
    # embedding = reducer.fit_transform(vectors)  # shape: (N, 3)
    #
    # return [
    #     EmbeddedPoint(track_id=t.track_id, x=float(pt[0]), y=float(pt[1]), z=float(pt[2]))
    #     for t, pt in zip(tracks, embedding)
    # ]

    # ------------------------------------------------------------------
    # PLACEHOLDER — random 3-D scatter (remove once UMAP is wired up)
    # ------------------------------------------------------------------
    import random
    import math

    points: list[EmbeddedPoint] = []
    for track in tracks:
        r = random.uniform(0, 50)
        theta = random.uniform(0, 2 * math.pi)
        phi = math.acos(random.uniform(-1, 1))
        points.append(
            EmbeddedPoint(
                track_id=track.track_id,
                x=r * math.sin(phi) * math.cos(theta),
                y=r * math.sin(phi) * math.sin(theta),
                z=r * math.cos(phi),
            )
        )
    return points
