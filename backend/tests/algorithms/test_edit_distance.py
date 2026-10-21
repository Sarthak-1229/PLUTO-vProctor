"""Tests for edit distance implementation."""
import pytest
from rapidfuzz.distance import Levenshtein as RapidLevenshtein
from backend.app.algorithms.edit_distance import levenshtein, is_fuzzy_match


@pytest.mark.parametrize("s,t,expected", [
    ("", "", 0),
    ("abc", "", 3),
    ("", "abc", 3),
    ("abc", "abc", 0),
    ("kitten", "sitting", 3),
    ("saturday", "sunday", 3),
    ("python", "cython", 1),
])
def test_levenshtein_values(s, t, expected):
    assert levenshtein(s, t) == expected


def test_matches_rapidfuzz():
    """Cross-check our implementation against rapidfuzz reference."""
    pairs = [("algorithm", "algorithmic"), ("machine", "learning"), ("neural", "lateral")]
    for s, t in pairs:
        our_val = levenshtein(s, t)
        ref_val = RapidLevenshtein.distance(s, t)
        assert our_val == ref_val, f"Mismatch for ({s!r}, {t!r}): ours={our_val}, ref={ref_val}"


def test_fuzzy_match_true():
    assert is_fuzzy_match("colour", "color") is True


def test_fuzzy_match_false():
    assert is_fuzzy_match("hello", "world", max_distance=2) is False
