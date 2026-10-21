"""Tests for sorting algorithms (merge sort, quick sort)."""
import random
import pytest
from backend.app.algorithms.sorting import merge_sort, quick_sort


def _random_list(n=200):
    return [random.randint(-1000, 1000) for _ in range(n)]


def test_merge_sort_ascending():
    arr = _random_list()
    result = merge_sort(arr)
    assert result == sorted(arr)


def test_merge_sort_descending():
    arr = _random_list()
    result = merge_sort(arr, reverse=True)
    assert result == sorted(arr, reverse=True)


def test_merge_sort_with_key():
    arr = [{"score": 5}, {"score": 1}, {"score": 3}]
    result = merge_sort(arr, key=lambda x: x["score"])
    assert [r["score"] for r in result] == [1, 3, 5]


def test_merge_sort_stable():
    arr = [(1, "b"), (1, "a"), (2, "c")]
    result = merge_sort(arr, key=lambda x: x[0])
    # Stable: (1,"b") appears before (1,"a") as in original
    assert result[0] == (1, "b")
    assert result[1] == (1, "a")


def test_quick_sort_ascending():
    arr = _random_list()
    result = quick_sort(arr)
    assert result == sorted(arr)


def test_quick_sort_descending():
    arr = _random_list()
    result = quick_sort(arr, reverse=True)
    assert result == sorted(arr, reverse=True)


def test_sort_edge_cases():
    assert merge_sort([]) == []
    assert merge_sort([42]) == [42]
    assert quick_sort([]) == []
