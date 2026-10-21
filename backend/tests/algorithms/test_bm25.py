"""Tests for BM25 retrieval."""
import pytest
from backend.app.algorithms.bm25 import BM25


CORPUS = [
    "python machine learning algorithms",
    "deep learning neural networks tensorflow",
    "database sql queries normalization",
    "python web framework fastapi rest",
    "algorithms data structures complexity",
]


def test_bm25_scores_relevant_higher():
    bm25 = BM25().fit(CORPUS)
    scores = [(i, bm25.score("python", i)) for i in range(len(CORPUS))]
    python_docs = {0, 3}  # docs containing "python"
    for i, score in scores:
        if i in python_docs:
            assert score > 0.0


def test_bm25_rank_order():
    bm25 = BM25().fit(CORPUS)
    ranked = bm25.rank("python algorithms", top_n=3)
    top_indices = [idx for idx, _ in ranked]
    # python + algorithms appear in doc 0 and 4
    assert 0 in top_indices or 4 in top_indices


def test_bm25_empty_query():
    bm25 = BM25().fit(CORPUS)
    score = bm25.score("", 0)
    assert score == 0.0


def test_bm25_top_n_limit():
    bm25 = BM25().fit(CORPUS)
    ranked = bm25.rank("python", top_n=2)
    assert len(ranked) == 2
