"""
Feature engineering for the PLUTO vProctor ML grader (core/aiml/grader_ml).

Turns a (candidate_answer, reference_text) pair into a small, bounded, dense
feature vector that classical scikit-learn estimators can score. The reference
is the gold answer at TRAIN time and the question's ideal_answer_points+keywords
at RUNTIME — both "the correct answer's text", so the learned mapping transfers.

All features are in [0,1] (GaussianNB / distance-model friendly) and CPU-cheap:
  cosine     TF-IDF cosine similarity (semantic overlap; the main signal)
  kw_cov     fraction of reference content-words present in the candidate
  jaccard    token-set Jaccard(candidate, reference)
  seq_ratio  difflib character-sequence ratio (order-sensitive similarity)
  len_cov    min(1, |candidate| / |reference|)  (did they say enough)
  substance  min(1, |candidate| / 50)           (absolute answer-length signal)

Self-contained (does NOT import eval_tier1) to avoid an import cycle: eval_tier1
imports the grader, which imports this module.
"""
import re
from difflib import SequenceMatcher
from typing import List, Sequence, Tuple

import numpy as np

FEATURE_NAMES = ["cosine", "kw_cov", "jaccard", "seq_ratio", "len_cov", "substance"]

_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")
_STOP = {"the", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
         "is", "are", "be", "as", "at", "by", "it", "this", "that", "you", "your",
         "we", "they", "how", "what", "why", "when", "which", "from", "a"}


def _tokens(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t]


def _content(text: str) -> set:
    return {t for t in _tokens(text) if len(t) > 3 and t not in _STOP}


class FeatureExtractor:
    """Fitted TF-IDF + pairwise lexical features. Persisted inside the grader artifact."""

    def __init__(self):
        self.vectorizer = None  # sklearn TfidfVectorizer, set by fit()

    def fit(self, corpus: Sequence[str]) -> "FeatureExtractor":
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = TfidfVectorizer(
            lowercase=True, stop_words="english", ngram_range=(1, 2),
            min_df=2, max_features=20000, sublinear_tf=True,
        )
        self.vectorizer.fit([c or "" for c in corpus])
        return self

    def _cosine(self, a: str, b: str) -> float:
        if self.vectorizer is None:
            return 0.0
        m = self.vectorizer.transform([a or "", b or ""])
        # TfidfVectorizer L2-normalizes rows by default -> dot product == cosine.
        return float((m[0] @ m[1].T).toarray()[0, 0])

    def pair_features(self, candidate: str, reference: str) -> np.ndarray:
        cand_t, ref_t = _tokens(candidate), _tokens(reference)
        cand_c, ref_c = _content(candidate), _content(reference)
        cosine = self._cosine(candidate, reference)
        kw_cov = (len(cand_c & ref_c) / len(ref_c)) if ref_c else 0.0
        union = cand_c | ref_c
        jaccard = (len(cand_c & ref_c) / len(union)) if union else 0.0
        seq_ratio = SequenceMatcher(None, (candidate or "").lower(),
                                    (reference or "").lower()).ratio()
        len_cov = min(1.0, len(cand_t) / max(1, len(ref_t)))
        substance = min(1.0, len(cand_t) / 50.0)
        return np.array([cosine, kw_cov, jaccard, seq_ratio, len_cov, substance],
                        dtype=float)

    def transform(self, pairs: Sequence[Tuple[str, str]]) -> np.ndarray:
        if not pairs:
            return np.empty((0, len(FEATURE_NAMES)))
        return np.vstack([self.pair_features(c, r) for c, r in pairs])
