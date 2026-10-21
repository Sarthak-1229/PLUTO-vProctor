"""Tests for TF-IDF, cosine similarity, and inverted index."""
import pytest
from backend.app.algorithms.similarity import (
    tokenize, TFIDFVectorizer, cosine_similarity, InvertedIndex
)


def test_tokenize():
    assert "python" in tokenize("Python is great!")
    assert "is" in tokenize("Python is great!")


def test_tfidf_fit_transform():
    corpus = ["python machine learning", "deep learning python", "database sql queries"]
    tfidf = TFIDFVectorizer().fit(corpus)
    vec = tfidf.transform("python learning")
    assert "python" in vec
    assert "learning" in vec
    assert vec["python"] > 0


def test_cosine_similarity_identical():
    corpus = ["python machine learning"]
    tfidf = TFIDFVectorizer().fit(corpus)
    vec = tfidf.transform("python machine learning")
    assert cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-6)


def test_cosine_similarity_different():
    corpus = ["apple orange", "quantum physics"]
    tfidf = TFIDFVectorizer().fit(corpus)
    va = tfidf.transform("apple orange")
    vb = tfidf.transform("quantum physics")
    assert cosine_similarity(va, vb) == pytest.approx(0.0, abs=1e-6)


def test_inverted_index():
    docs = ["python is great", "java is popular", "python and java are both popular"]
    index = InvertedIndex().build(docs)
    results = index.query("python")
    assert 0 in results
    assert 2 in results
    assert 1 not in results


def test_inverted_index_empty():
    index = InvertedIndex().build(["hello world"])
    assert index.query("xyz") == []
