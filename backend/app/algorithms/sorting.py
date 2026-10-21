"""Merge Sort and Quick Sort hand implementations.

Used to rank questions by relevance score and order deduction events by timestamp.

Merge Sort:
    Time:  O(N log N) best/average/worst (stable)
    Space: O(N) auxiliary

Quick Sort:
    Time:  O(N log N) average, O(N^2) worst case (mitigated by median-of-3 pivot)
    Space: O(log N) stack frames average
"""
from __future__ import annotations
from typing import Any, Callable, List, TypeVar

T = TypeVar("T")


def merge_sort(arr: List[Any], key: Callable[[Any], Any] = lambda x: x, reverse: bool = False) -> List[Any]:
    """Stable merge sort implementation.

    Args:
        arr: List to sort (not mutated; returns new list).
        key: Function to extract comparison key. Default is identity.
        reverse: If True, sort in descending order.

    Returns:
        New sorted list.

    Time:  O(N log N)
    Space: O(N)
    """
    if len(arr) <= 1:
        return list(arr)

    mid = len(arr) // 2
    left = merge_sort(arr[:mid], key=key, reverse=reverse)
    right = merge_sort(arr[mid:], key=key, reverse=reverse)
    return _merge(left, right, key=key, reverse=reverse)


def _merge(left: List[Any], right: List[Any], key: Callable, reverse: bool) -> List[Any]:
    result: List[Any] = []
    i = j = 0
    while i < len(left) and j < len(right):
        lk, rk = key(left[i]), key(right[j])
        if (lk <= rk) ^ reverse:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


def quick_sort(arr: List[Any], key: Callable[[Any], Any] = lambda x: x, reverse: bool = False) -> List[Any]:
    """Quick sort with median-of-three pivot selection (in-place on a copy).

    Args:
        arr: List to sort.
        key: Function to extract comparison key.
        reverse: If True, sort in descending order.

    Returns:
        New sorted list.

    Time:  O(N log N) average
    Space: O(log N) stack
    """
    arr = list(arr)
    _qs(arr, 0, len(arr) - 1, key=key, reverse=reverse)
    return arr


def _median_of_three(arr: List[Any], lo: int, hi: int, key: Callable) -> int:
    mid = (lo + hi) // 2
    triple = [(key(arr[lo]), lo), (key(arr[mid]), mid), (key(arr[hi]), hi)]
    triple.sort()
    return triple[1][1]


def _qs(arr: List[Any], lo: int, hi: int, key: Callable, reverse: bool) -> None:
    if lo >= hi:
        return
    pivot_idx = _median_of_three(arr, lo, hi, key)
    arr[pivot_idx], arr[hi] = arr[hi], arr[pivot_idx]
    pivot_key = key(arr[hi])
    i = lo - 1
    for j in range(lo, hi):
        cmp = key(arr[j]) <= pivot_key if not reverse else key(arr[j]) >= pivot_key
        if cmp:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i + 1], arr[hi] = arr[hi], arr[i + 1]
    p = i + 1
    _qs(arr, lo, p - 1, key=key, reverse=reverse)
    _qs(arr, p + 1, hi, key=key, reverse=reverse)
