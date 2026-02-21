"""
Similarity module -- superseded by Actian VectorAI DB.

Actian VectorAI DB now handles all nearest-neighbour search via its built-in
COSINE distance index (HNSW). The high-level call lives in db.search_similar().

This file is kept as a reference / fallback for:
  - Unit tests that run without the DB container
  - Understanding the underlying math
  - Offline / in-memory experimentation
"""

import math
from dataclasses import dataclass


@dataclass
class SimilarityResult:
    song_id: str
    score: float  # cosine similarity in [0, 1]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two equal-length vectors.
    Returns a value in [-1, 1]; for audio features expect [0, 1].
    """
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def find_topological_twins(
    query_vector: list[float],
    dataset: dict[str, list[float]],
    top_k: int = 5,
) -> list[SimilarityResult]:
    """
    Brute-force nearest-neighbour search over `dataset`.

    Args:
        query_vector: 12-D feature vector for the query song.
        dataset: Mapping of song_id -> 12-D feature vector.
        top_k: How many results to return.

    Returns:
        List of SimilarityResult sorted by descending similarity.

    NOTE: In production this is replaced by db.search_similar(), which
    delegates to Actian VectorAI DB's HNSW index for O(log n) lookup.
    """
    results: list[SimilarityResult] = []

    for song_id, vector in dataset.items():
        score = cosine_similarity(query_vector, vector)
        results.append(SimilarityResult(song_id=song_id, score=score))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]
