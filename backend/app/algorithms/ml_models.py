"""Thin wrappers around scikit-learn ML models used in PLUTO vProctor.

These are NOT hand-implemented algorithms; they delegate to scikit-learn.
The hand-implemented counterparts are in smoothing.py (Naive Bayes) and
similarity.py (TF-IDF / cosine).

This module provides:
- LogisticRegression screening classifier
- MultinomialNaiveBayes domain classifier
- Lightweight training + serialisation helpers

All thresholds and hyperparameters come from config.py.
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.config import settings


class ScreeningClassifier:
    """Logistic Regression pass/fail screening classifier.

    Uses TF-IDF features from resume text vs job description.
    """

    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        self.model = LogisticRegression(max_iter=1000, class_weight="balanced")
        self._fitted = False

    def fit(self, texts: List[str], labels: List[int]) -> "ScreeningClassifier":
        """Fit on labelled resume-job concatenations.

        Args:
            texts: List of 'resume + job_description' strings.
            labels: 1 = pass, 0 = fail.

        Returns:
            Self.
        """
        X = self.vectorizer.fit_transform(texts)
        self.model.fit(X, labels)
        self._fitted = True
        return self

    def predict_proba(self, text: str) -> float:
        """Return probability of pass (class 1).

        Args:
            text: Concatenated resume + job description.

        Returns:
            Float in [0, 1].
        """
        X = self.vectorizer.transform([text])
        proba = self.model.predict_proba(X)[0]
        return float(proba[1])

    def save(self, path: Path) -> None:
        joblib.dump({"vectorizer": self.vectorizer, "model": self.model}, path)

    @classmethod
    def load(cls, path: Path) -> "ScreeningClassifier":
        obj = cls()
        data = joblib.load(path)
        obj.vectorizer = data["vectorizer"]
        obj.model = data["model"]
        obj._fitted = True
        return obj


class DomainClassifier:
    """Multinomial Naive Bayes domain/topic classifier for questions.

    Predicts the domain label (e.g., 'python', 'databases', 'algorithms')
    from question text.
    """

    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(max_features=3000)
        self.model = MultinomialNB()
        self._fitted = False

    def fit(self, questions: List[str], domains: List[str]) -> "DomainClassifier":
        X = self.vectorizer.fit_transform(questions)
        self.model.fit(X, domains)
        self._fitted = True
        return self

    def predict(self, question: str) -> Tuple[str, float]:
        """Predict domain and confidence for a single question.

        Returns:
            Tuple of (domain_label, probability).
        """
        X = self.vectorizer.transform([question])
        label = self.model.predict(X)[0]
        proba = np.max(self.model.predict_proba(X)[0])
        return str(label), float(proba)

    def save(self, path: Path) -> None:
        joblib.dump({"vectorizer": self.vectorizer, "model": self.model}, path)

    @classmethod
    def load(cls, path: Path) -> "DomainClassifier":
        obj = cls()
        data = joblib.load(path)
        obj.vectorizer = data["vectorizer"]
        obj.model = data["model"]
        obj._fitted = True
        return obj
