"""RAKE-style keyword extraction.

Used to extract expected_keywords from question+answer pairs and build
the skills taxonomy from the datasets.

RAKE (Rapid Automatic Keyword Extraction):
    1. Split text into candidate phrases using stop-word boundaries.
    2. Score each word by degree / frequency.
    3. Score each phrase as the sum of member word scores.

Time:  O(T) where T = number of tokens
Space: O(T)
"""
from __future__ import annotations
import math
import re
from collections import Counter
from typing import Dict, List, Tuple

_STOP_WORDS: frozenset = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "this", "that", "these", "those",
    "it", "its", "from", "as", "by", "about", "into", "through",
    "what", "which", "who", "how", "when", "where", "why", "if",
    "not", "no", "so", "then", "than", "also", "i", "you", "we", "they",
    "he", "she", "them", "us", "me", "our", "your", "their",
})

_PHRASE_DELIMITERS = re.compile(r"[,.:;!?\n\t\"|()<>{}]+")


def _extract_candidate_phrases(text: str) -> List[List[str]]:
    """Split text into candidate keyword phrases on stop words and punctuation."""
    text = text.lower()
    chunks = _PHRASE_DELIMITERS.split(text)
    phrases: List[List[str]] = []
    for chunk in chunks:
        words = chunk.split()
        phrase: List[str] = []
        for w in words:
            w = w.strip("'\"")
            if w in _STOP_WORDS or not re.search(r"[a-z]", w):
                if phrase:
                    phrases.append(phrase)
                phrase = []
            else:
                phrase.append(w)
        if phrase:
            phrases.append(phrase)
    return phrases


def rake_keywords(text: str, top_n: int = 10) -> List[Tuple[str, float]]:
    """Extract keywords from text using RAKE.

    Args:
        text: Input document (question or answer).
        top_n: Maximum number of top-scoring keywords to return.

    Returns:
        List of (phrase_string, score) sorted by score descending.
    """
    phrases = _extract_candidate_phrases(text)
    # Word frequency and degree
    word_freq: Counter = Counter()
    word_degree: Counter = Counter()

    for phrase in phrases:
        for word in phrase:
            word_freq[word] += 1
            word_degree[word] += len(phrase) - 1

    # Word score = degree / frequency
    word_score: Dict[str, float] = {
        w: (word_degree[w] + word_freq[w]) / max(word_freq[w], 1)
        for w in word_freq
    }

    # Phrase score = sum of word scores
    phrase_scores: List[Tuple[str, float]] = []
    seen: set[str] = set()
    for phrase in phrases:
        phrase_str = " ".join(phrase)
        if phrase_str in seen or not phrase_str.strip():
            continue
        seen.add(phrase_str)
        score = sum(word_score.get(w, 0.0) for w in phrase)
        phrase_scores.append((phrase_str, score))

    phrase_scores.sort(key=lambda x: x[1], reverse=True)
    return phrase_scores[:top_n]


def extract_top_keywords(text: str, top_n: int = 10) -> List[str]:
    """Return only the keyword strings (no scores) from RAKE extraction.

    Args:
        text: Input document.
        top_n: Number of keywords to extract.

    Returns:
        List of keyword phrase strings.
    """
    return [kw for kw, _ in rake_keywords(text, top_n)]
