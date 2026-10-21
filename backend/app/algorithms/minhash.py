"""MinHash / LSH for near-duplicate question detection across datasets.

Used for cross-split deduplication of questions in data/ and data1/.

MinHash:
    Time:  O(N * H) where N = shingle count, H = hash permutations
    Space: O(H) per document signature
Jaccard estimate error: ~1/sqrt(H)
"""
from __future__ import annotations
import hashlib
import math
from typing import List, Set, Tuple

from backend.app.config import settings

# Large prime used as hash modulus
_MERSENNE_PRIME = (1 << 61) - 1


def shingles(text: str, k: int = 3) -> Set[str]:
    """Generate character k-shingles from text.

    Args:
        text: Input string (lowercased, whitespace-normalised).
        k: Shingle length in characters. Default 3.

    Returns:
        Set of k-character substrings.
    """
    text = " ".join(text.lower().split())
    return {text[i: i + k] for i in range(max(0, len(text) - k + 1))}


def _hash_shingle(shingle: str, a: int, b: int) -> int:
    """Universal hash function: h(x) = (a*x + b) mod p.

    x is the integer hash of the shingle string.
    """
    x = int(hashlib.sha1(shingle.encode("utf-8")).hexdigest(), 16)
    return ((a * x + b) % _MERSENNE_PRIME)


def minhash_signature(text: str, num_perm: int = settings.MINHASH_NUM_PERMUTATIONS) -> List[int]:
    """Compute MinHash signature vector for a piece of text.

    Args:
        text: Input string.
        num_perm: Number of hash permutations (= signature length).

    Returns:
        List of num_perm minimum hash values.
    """
    sg = shingles(text)
    if not sg:
        return [0] * num_perm
    # Deterministic (a, b) pairs derived from permutation index
    import random
    rng = random.Random(42)
    params = [(rng.randint(1, _MERSENNE_PRIME - 1), rng.randint(0, _MERSENNE_PRIME - 1)) for _ in range(num_perm)]
    signature: List[int] = []
    for a, b in params:
        min_hash = min(_hash_shingle(s, a, b) for s in sg)
        signature.append(min_hash)
    return signature


def jaccard_from_signatures(sig_a: List[int], sig_b: List[int]) -> float:
    """Estimate Jaccard similarity from two MinHash signatures.

    Args:
        sig_a: Signature of document A.
        sig_b: Signature of document B.

    Returns:
        Estimated Jaccard similarity in [0, 1].
    """
    if len(sig_a) != len(sig_b):
        raise ValueError("Signature lengths must match")
    matches = sum(a == b for a, b in zip(sig_a, sig_b))
    return matches / len(sig_a)


def is_near_duplicate(
    text_a: str,
    text_b: str,
    threshold: float = settings.MINHASH_JACCARD_THRESHOLD,
    num_perm: int = settings.MINHASH_NUM_PERMUTATIONS,
) -> bool:
    """Check if two texts are near-duplicates by MinHash Jaccard estimate.

    Args:
        text_a: First document string.
        text_b: Second document string.
        threshold: Jaccard threshold above which texts are considered duplicates.
        num_perm: Number of hash permutations.

    Returns:
        True if estimated Jaccard >= threshold.
    """
    sig_a = minhash_signature(text_a, num_perm)
    sig_b = minhash_signature(text_b, num_perm)
    return jaccard_from_signatures(sig_a, sig_b) >= threshold
