"""Levenshtein edit distance (dynamic programming).

Used for fuzzy skill matching and filler-word variant detection.

Time complexity:  O(M * N) where M, N = lengths of the two strings
Space complexity: O(M * N)  (O(N) with rolling-array optimization)
"""
from __future__ import annotations


def levenshtein(s: str, t: str) -> int:
    """Compute the Levenshtein edit distance between two strings.

    Operations: insertion, deletion, substitution each cost 1.

    Args:
        s: Source string.
        t: Target string.

    Returns:
        Integer edit distance.
    """
    m, n = len(s), len(t)
    # Space-optimised: two rows only
    prev = list(range(n + 1))
    curr = [0] * (n + 1)

    for i in range(1, m + 1):
        curr[0] = i
        for j in range(1, n + 1):
            if s[i - 1] == t[j - 1]:
                curr[j] = prev[j - 1]
            else:
                curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
        prev, curr = curr, prev

    return prev[n]


def is_fuzzy_match(s: str, t: str, max_distance: int = 2) -> bool:
    """Return True if edit distance between s and t is <= max_distance.

    Args:
        s: First string (case-insensitive, lowercased internally).
        t: Second string.
        max_distance: Maximum allowed edit distance. Default 2.

    Returns:
        True if strings are within the edit distance threshold.
    """
    return levenshtein(s.lower(), t.lower()) <= max_distance
