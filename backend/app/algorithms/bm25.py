"""BM25 (Okapi BM25) — own implementation.

Used for:
- Question-to-answer retrieval
- Answer relevance scoring as a feature for the hybrid evaluator

Time:
    fit:   O(D * T) where D = corpus size, T = tokens per document
    score: O(T_query) per document
Space: O(D * V) for term frequencies
"""
from __future__ import annotations
import math
from collections import Counter
from typing import Dict, List, Tuple

from backend.app.config import settings
from backend.app.algorithms.similarity import tokenize


class BM25:
    """Okapi BM25 retrieval model.

    Attributes:
        k1: Term frequency saturation parameter. From config.
        b:  Field length normalisation parameter. From config.
    """

    def __init__(self, k1: float = settings.BM25_K1, b: float = settings.BM25_B) -> None:
        self.k1 = k1
        self.b = b
        self._corpus_tokens: List[List[str]] = []
        self._df: Dict[str, int] = {}       # Document frequency per term
        self._tf: List[Dict[str, int]] = [] # Term frequency per document
        self._avgdl: float = 0.0
        self._n: int = 0

    def fit(self, corpus: List[str]) -> "BM25":
        """Build BM25 index from corpus.

        Args:
            corpus: List of raw text strings.

        Returns:
            Self.
        """
        self._n = len(corpus)
        self._corpus_tokens = [tokenize(doc) for doc in corpus]
        self._tf = [Counter(tokens) for tokens in self._corpus_tokens]
        lengths = [len(t) for t in self._corpus_tokens]
        self._avgdl = sum(lengths) / self._n if self._n else 1.0
        self._df = {}
        for tokens in self._corpus_tokens:
            for t in set(tokens):
                self._df[t] = self._df.get(t, 0) + 1
        return self

    def score(self, query: str, doc_idx: int) -> float:
        """Compute BM25 score for a single document.

        Args:
            query: Raw query string.
            doc_idx: Index of the document in the fitted corpus.

        Returns:
            BM25 relevance score (float >= 0).
        """
        query_tokens = tokenize(query)
        tf = self._tf[doc_idx]
        dl = len(self._corpus_tokens[doc_idx])
        score = 0.0
        for t in query_tokens:
            if t not in tf:
                continue
            df = self._df.get(t, 0)
            idf = math.log((self._n - df + 0.5) / (df + 0.5) + 1)
            tf_val = tf[t]
            numerator = tf_val * (self.k1 + 1)
            denominator = tf_val + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
            score += idf * numerator / denominator
        return score

    def rank(self, query: str, top_n: int = 10) -> List[Tuple[int, float]]:
        """Return top-N document indices ranked by BM25 score.

        Args:
            query: Raw query text.
            top_n: Maximum number of results to return.

        Returns:
            List of (doc_index, score) sorted by score descending.
        """
        scores = [(i, self.score(query, i)) for i in range(self._n)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]
