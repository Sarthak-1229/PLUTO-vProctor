"""Maximal Marginal Relevance (MMR) for diverse question selection.

Used to select a final interview question set that balances
relevance to the candidate's skill profile with topic diversity.

Greedy MMR:
    Time:  O(K * N) where K = questions to select, N = candidate pool
    Space: O(N * D) for pre-computed embeddings
"""
from __future__ import annotations
import math
from typing import Callable, Dict, List, Optional, Tuple

from backend.app.config import settings


def _cosine(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two dense vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def mmr_select(
    query_embedding: List[float],
    candidate_embeddings: List[List[float]],
    candidate_scores: List[float],
    k: int,
    lambda_: float = settings.MMR_LAMBDA,
) -> List[int]:
    """Select k candidates by Maximal Marginal Relevance.

    MMR score for candidate i:
        MMR_i = lambda_ * relevance(i, query) - (1 - lambda_) * max_j(sim(i, j))
    where j iterates over already-selected candidates.

    Args:
        query_embedding:      Dense embedding of the query / skill profile.
        candidate_embeddings: Embeddings for each candidate question.
        candidate_scores:     Pre-computed relevance scores (e.g., BM25 or cosine).
        k:                    Number of items to select.
        lambda_:              Trade-off: 1.0 = pure relevance, 0.0 = pure diversity.

    Returns:
        List of selected indices into candidate_embeddings, in selection order.

    Time:  O(K * N * D) where D = embedding dimension
    Space: O(N)
    """
    if not candidate_embeddings or k <= 0:
        return []

    n = len(candidate_embeddings)
    k = min(k, n)
    selected: List[int] = []
    remaining = list(range(n))

    # Normalise relevance scores to [0, 1]
    max_s = max(candidate_scores) if candidate_scores else 1.0
    rel = [s / max_s if max_s > 0 else 0.0 for s in candidate_scores]

    for _ in range(k):
        best_idx: Optional[int] = None
        best_score = float("-inf")
        for i in remaining:
            if not selected:
                sim_to_selected = 0.0
            else:
                sim_to_selected = max(
                    _cosine(candidate_embeddings[i], candidate_embeddings[j])
                    for j in selected
                )
            mmr_score = lambda_ * rel[i] - (1 - lambda_) * sim_to_selected
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i
        if best_idx is None:
            break
        selected.append(best_idx)
        remaining.remove(best_idx)

    return selected
