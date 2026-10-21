"""Smoothing utilities for score distributions.

Implements Laplace (add-alpha) smoothing for Naive Bayes probability tables
and a simple score normalisation utility.

Time:  O(V) where V = vocabulary size
Space: O(V)
"""
from __future__ import annotations
import math
from collections import Counter
from typing import Dict, List, Tuple


class LaplaceSmoothing:
    """Multinomial Naive Bayes log-probability table with Laplace (add-alpha) smoothing.

    Attributes:
        alpha: Smoothing hyperparameter. Default 1.0 (add-one smoothing).
    """

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self._class_log_prior: Dict[str, float] = {}
        self._feature_log_prob: Dict[str, Dict[str, float]] = {}  # class -> token -> log_prob

    def fit(self, X: List[List[str]], y: List[str]) -> "LaplaceSmoothing":
        """Fit the Naive Bayes model.

        Args:
            X: Tokenized documents (list of token lists).
            y: Class labels.

        Returns:
            Self.
        """
        classes = list(set(y))
        n_docs = len(y)
        # Collect all vocabulary
        vocab: set[str] = {t for doc in X for t in doc}
        v = len(vocab)

        for cls in classes:
            docs_in_cls = [X[i] for i in range(n_docs) if y[i] == cls]
            self._class_log_prior[cls] = math.log(len(docs_in_cls) / n_docs)
            # Token counts across all docs in this class
            token_count: Counter = Counter(t for doc in docs_in_cls for t in doc)
            total = sum(token_count.values())
            self._feature_log_prob[cls] = {
                t: math.log((token_count.get(t, 0) + self.alpha) / (total + self.alpha * v))
                for t in vocab
            }

        return self

    def predict(self, tokens: List[str]) -> Tuple[str, Dict[str, float]]:
        """Classify a tokenized document.

        Args:
            tokens: List of tokens from the document.

        Returns:
            Tuple of (predicted_class, {class: log_score}).
        """
        scores: Dict[str, float] = {}
        for cls, log_prior in self._class_log_prior.items():
            log_likelihood = sum(
                self._feature_log_prob[cls].get(t, math.log(self.alpha / (1 + self.alpha)))
                for t in tokens
            )
            scores[cls] = log_prior + log_likelihood
        predicted = max(scores, key=scores.__getitem__)
        return predicted, scores


def min_max_normalize(values: List[float]) -> List[float]:
    """Normalise a list of values to [0, 1] using min-max scaling.

    Args:
        values: List of floats.

    Returns:
        Normalised list. If all values are equal, returns list of zeros.
    """
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]
