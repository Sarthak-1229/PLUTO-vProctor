"""Tests for Trie implementation."""
import pytest
from backend.app.algorithms.trie import Trie


def test_insert_and_search():
    t = Trie()
    t.insert("python")
    t.insert("pytorch")
    t.insert("pandas")
    assert t.search("python") is True
    assert t.search("pytorch") is True
    assert t.search("py") is False
    assert t.search("ruby") is False


def test_starts_with():
    t = Trie()
    t.insert("machine learning")
    t.insert("machine vision")
    assert t.starts_with("machine") is True
    assert t.starts_with("deep") is False


def test_autocomplete():
    t = Trie()
    for word in ["fastapi", "fastlane", "fast", "flask"]:
        t.insert(word)
    results = t.autocomplete("fast")
    assert "fast" in results
    assert "fastapi" in results
    assert "fastlane" in results
    assert "flask" not in results


def test_case_insensitive():
    t = Trie()
    t.insert("Python")
    assert t.search("python") is True
    assert t.search("PYTHON") is True


def test_empty_trie():
    t = Trie()
    assert t.search("anything") is False
    assert t.starts_with("a") is False
    assert t.autocomplete("a") == []
