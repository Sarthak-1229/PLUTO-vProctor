"""TF-IDF + cosine similarity.

Used for:
- Resume-job matching (bag-of-words overlap)
- Answer-to-expected-answer similarity scoring
- Inverted index-based question retrieval by skill/topic

Time:
    fit:       O(D * T) where D = documents, T = unique terms
    transform: O(T) per document
    cosine:    O(V) where V = vocabulary size
Space: O(D * V) for the full TF-IDF matrix
"""
from __future__ import annotations
import math
from collections import Counter
from typing import Dict, List, Optional, Tuple


def tokenize(text: str) -> List[str]:
    """Lowercase, split on whitespace/punctuation.

    Args:
        text: Raw input string.

    Returns:
        List of lowercase tokens.
    """
    import re
    return re.findall(r"[a-z0-9']+", text.lower())


class TFIDFVectorizer:
    """Hand-implemented TF-IDF vectorizer.

    Attributes:
        vocab:  Vocabulary mapping token -> index (built during fit).
        idf:    IDF scores per token (built during fit).
    """

    def __init__(self) -> None:
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self._n_docs: int = 0

    def fit(self, corpus: List[str]) -> "TFIDFVectorizer":
        """Build vocabulary and IDF table from a corpus.

        Args:
            corpus: List of raw text strings.

        Returns:
            Self (for method chaining).
        """
        self._n_docs = len(corpus)
        doc_freq: Counter = Counter()
        tokenized = [tokenize(doc) for doc in corpus]
        for tokens in tokenized:
            for t in set(tokens):
                doc_freq[t] += 1
        self.vocab = {t: i for i, t in enumerate(sorted(doc_freq))}
        N = self._n_docs
        self.idf = {
            t: math.log((N + 1) / (df + 1)) + 1.0
            for t, df in doc_freq.items()
        }
        return self

    def transform(self, text: str) -> Dict[str, float]:
        """Convert a single document to a TF-IDF weighted sparse vector.

        Args:
            text: Raw input string.

        Returns:
            Dict mapping token -> tfidf_weight (only in-vocabulary tokens).
        """
        tokens = tokenize(text)
        if not tokens:
            return {}
        tf: Counter = Counter(tokens)
        total = len(tokens)
        vec: Dict[str, float] = {}
        for t, count in tf.items():
            if t in self.idf:
                vec[t] = (count / total) * self.idf[t]
        return vec


def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse TF-IDF vectors.

    Args:
        vec_a: First sparse vector (token -> weight).
        vec_b: Second sparse vector (token -> weight).

    Returns:
        Cosine similarity in [0, 1]. Returns 0.0 if either vector is zero.

    Time:  O(min(|A|, |B|))
    """
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in vec_a if t in vec_b)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InvertedIndex:
    """Hash-map inverted index for question retrieval by skill/topic token.

    Time:
        build: O(D * T)
        query: O(T_query + sum of posting_list lengths)
    Space: O(D * T)
    """

    def __init__(self) -> None:
        self._index: Dict[str, List[int]] = {}

    def build(self, documents: List[str]) -> "InvertedIndex":
        """Index all documents.

        Args:
            documents: List of text strings (one per question).

        Returns:
            Self.
        """
        self._index = {}
        for doc_id, text in enumerate(documents):
            for token in set(tokenize(text)):
                self._index.setdefault(token, []).append(doc_id)
        return self

    def query(self, query_text: str) -> List[int]:
        """Return union of all doc IDs matching any token in query.

        Args:
            query_text: Free-text query string.

        Returns:
            Sorted list of unique matching document indices.
        """
        matched: set[int] = set()
        for token in set(tokenize(query_text)):
            matched.update(self._index.get(token, []))
        return sorted(matched)
