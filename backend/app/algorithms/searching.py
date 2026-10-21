"""Binary search implementations.

Used for: locating proctoring deduction events near a video timestamp,
threshold lookups in sorted scoring tables.

Time:  O(log N)
Space: O(1)
"""
from __future__ import annotations
from typing import Any, Callable, List, Optional, Tuple


def binary_search(arr: List[Any], target: Any, key: Callable[[Any], Any] = lambda x: x) -> int:
    """Find the index of target in a sorted list.

    Args:
        arr: Sorted list of elements.
        target: The value to search for.
        key: Function to extract comparison key. Default is identity.

    Returns:
        Index of target in arr, or -1 if not found.

    Time:  O(log N)
    Space: O(1)
    """
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        mk = key(arr[mid])
        if mk == target:
            return mid
        elif mk < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


def lower_bound(arr: List[Any], target: Any, key: Callable[[Any], Any] = lambda x: x) -> int:
    """Return the first index where key(arr[i]) >= target (leftmost insertion point).

    Args:
        arr: Sorted list.
        target: Comparison value.
        key: Key extractor function.

    Returns:
        Integer index in [0, len(arr)].
    """
    lo, hi = 0, len(arr)
    while lo < hi:
        mid = (lo + hi) // 2
        if key(arr[mid]) < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def upper_bound(arr: List[Any], target: Any, key: Callable[[Any], Any] = lambda x: x) -> int:
    """Return the first index where key(arr[i]) > target (rightmost insertion point).

    Args:
        arr: Sorted list.
        target: Comparison value.
        key: Key extractor function.

    Returns:
        Integer index in [0, len(arr)].
    """
    lo, hi = 0, len(arr)
    while lo < hi:
        mid = (lo + hi) // 2
        if key(arr[mid]) <= target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def find_closest_timestamp(timestamps: List[float], query: float) -> Tuple[int, float]:
    """Find the index and value of the closest timestamp to query in a sorted list.

    Used for locating proctoring deductions near a video timestamp.

    Args:
        timestamps: Sorted list of float timestamps (seconds).
        query: Target timestamp to find the nearest entry for.

    Returns:
        Tuple of (index, value) of the closest timestamp.
        Returns (-1, 0.0) if timestamps is empty.
    """
    if not timestamps:
        return -1, 0.0
    idx = lower_bound(timestamps, query)
    if idx == 0:
        return 0, timestamps[0]
    if idx == len(timestamps):
        return len(timestamps) - 1, timestamps[-1]
    before = timestamps[idx - 1]
    after = timestamps[idx]
    if abs(after - query) < abs(before - query):
        return idx, after
    return idx - 1, before
