"""Tests for binary search algorithms."""
import bisect
import random
import pytest
from backend.app.algorithms.searching import (
    binary_search, lower_bound, upper_bound, find_closest_timestamp
)


def test_binary_search_found():
    arr = [1, 3, 5, 7, 9, 11]
    assert binary_search(arr, 7) == 3
    assert binary_search(arr, 1) == 0
    assert binary_search(arr, 11) == 5


def test_binary_search_not_found():
    arr = [2, 4, 6, 8]
    assert binary_search(arr, 5) == -1
    assert binary_search(arr, 10) == -1


def test_lower_bound_matches_bisect():
    arr = sorted(random.sample(range(200), 50))
    for target in range(201):
        assert lower_bound(arr, target) == bisect.bisect_left(arr, target)


def test_upper_bound_matches_bisect():
    arr = sorted(random.sample(range(200), 50))
    for target in range(201):
        assert upper_bound(arr, target) == bisect.bisect_right(arr, target)


def test_find_closest_timestamp():
    ts = [0.0, 1.0, 2.5, 4.0, 5.5]
    idx, val = find_closest_timestamp(ts, 2.3)
    assert val == pytest.approx(2.5)
    idx2, val2 = find_closest_timestamp(ts, 0.0)
    assert val2 == pytest.approx(0.0)


def test_find_closest_empty():
    assert find_closest_timestamp([], 1.5) == (-1, 0.0)
