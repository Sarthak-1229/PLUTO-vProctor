"""KMP and Rabin-Karp string search algorithms.

Used for phrase / filler-word searching in transcript text.

KMP:
    Time:  O(N + M) where N = text length, M = pattern length
    Space: O(M) for the failure function table

Rabin-Karp:
    Time:  O(N + M) average, O(N*M) worst case (hash collisions)
    Space: O(1)
"""
from __future__ import annotations
from typing import List


def _kmp_failure(pattern: str) -> List[int]:
    """Build the KMP failure (partial match) table.

    Args:
        pattern: The search pattern.

    Returns:
        List of integers representing the longest proper prefix-suffix lengths.
    """
    m = len(pattern)
    fail = [0] * m
    j = 0
    for i in range(1, m):
        while j > 0 and pattern[i] != pattern[j]:
            j = fail[j - 1]
        if pattern[i] == pattern[j]:
            j += 1
        fail[i] = j
    return fail


def kmp_search(text: str, pattern: str) -> List[int]:
    """Find all start positions of pattern in text using KMP.

    Args:
        text: The text to search in.
        pattern: The pattern to search for.

    Returns:
        List of 0-indexed start positions where pattern occurs in text.
        Empty list if pattern not found or pattern is empty.
    """
    if not pattern:
        return []
    n, m = len(text), len(pattern)
    fail = _kmp_failure(pattern)
    positions: List[int] = []
    j = 0
    for i in range(n):
        while j > 0 and text[i] != pattern[j]:
            j = fail[j - 1]
        if text[i] == pattern[j]:
            j += 1
        if j == m:
            positions.append(i - m + 1)
            j = fail[j - 1]
    return positions


def rabin_karp_search(text: str, pattern: str, base: int = 31, mod: int = 10**9 + 7) -> List[int]:
    """Find all start positions of pattern in text using Rabin-Karp rolling hash.

    Args:
        text: The text to search in.
        pattern: The pattern to search for.
        base: Hash base (prime near alphabet size). Default 31.
        mod: Large prime for modular arithmetic. Default 10^9+7.

    Returns:
        List of 0-indexed start positions where pattern occurs in text.
    """
    if not pattern or len(pattern) > len(text):
        return []
    n, m = len(text), len(pattern)
    pattern_hash = 0
    text_hash = 0
    power = 1
    positions: List[int] = []

    for i in range(m):
        pattern_hash = (pattern_hash * base + ord(pattern[i])) % mod
        text_hash = (text_hash * base + ord(text[i])) % mod
        if i > 0:
            power = (power * base) % mod

    for i in range(n - m + 1):
        if text_hash == pattern_hash:
            # Verify match (avoid hash collision false positives)
            if text[i:i + m] == pattern:
                positions.append(i)
        if i < n - m:
            text_hash = (text_hash - ord(text[i]) * power) % mod
            text_hash = (text_hash * base + ord(text[i + m])) % mod
            text_hash = (text_hash + mod) % mod

    return positions
