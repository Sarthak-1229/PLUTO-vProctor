"""Tests for keyword extraction (RAKE)."""
import pytest
from backend.app.algorithms.keyword_extraction import rake_keywords, extract_top_keywords


def test_rake_returns_keywords():
    text = "Python machine learning algorithms are used in artificial intelligence applications"
    kws = rake_keywords(text, top_n=5)
    assert len(kws) > 0
    assert all(isinstance(kw, str) and isinstance(score, float) for kw, score in kws)


def test_rake_scores_nonnegative():
    text = "Deep learning neural networks for computer vision tasks"
    for kw, score in rake_keywords(text):
        assert score >= 0.0


def test_extract_top_keywords_returns_strings():
    text = "FastAPI REST API development with Python asynchronous programming"
    kws = extract_top_keywords(text, top_n=5)
    assert all(isinstance(k, str) for k in kws)
    assert len(kws) <= 5


def test_rake_empty():
    assert rake_keywords("", top_n=5) == []
    assert extract_top_keywords("") == []


def test_rake_stop_word_only():
    kws = rake_keywords("the and or but")
    assert kws == []
