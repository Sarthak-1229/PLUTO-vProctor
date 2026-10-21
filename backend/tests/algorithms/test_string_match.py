"""Tests for KMP and Rabin-Karp string search algorithms."""
import pytest
from backend.app.algorithms.string_match import kmp_search, rabin_karp_search


@pytest.mark.parametrize("text,pattern,expected", [
    ("ababcabcabababd", "ababd", [10]),
    ("aabaabaab", "aab", [0, 3, 6]),
    ("hello world", "world", [6]),
    ("aaaa", "aa", [0, 1, 2]),
    ("abc", "xyz", []),
    ("", "a", []),
    ("abc", "", []),
])
def test_kmp_search(text, pattern, expected):
    assert kmp_search(text, pattern) == expected


@pytest.mark.parametrize("text,pattern,expected", [
    ("hello world", "world", [6]),
    ("aaaa", "aa", [0, 1, 2]),
    ("aabaabaab", "aab", [0, 3, 6]),
    ("abc", "xyz", []),
    ("", "a", []),
])
def test_rabin_karp_search(text, pattern, expected):
    assert rabin_karp_search(text, pattern) == expected


def test_kmp_and_rk_agree():
    """KMP and Rabin-Karp should produce identical results."""
    text = "the quick brown fox jumped over the lazy dog"
    pattern = "the"
    assert kmp_search(text, pattern) == rabin_karp_search(text, pattern)
