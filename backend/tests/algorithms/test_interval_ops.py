"""Tests for interval merging and operations."""
import pytest
from backend.app.algorithms.interval_ops import merge_intervals, total_duration, find_violations_near


def test_merge_overlapping():
    intervals = [(1.0, 3.0), (2.0, 5.0), (6.0, 8.0)]
    result = merge_intervals(intervals)
    assert result == [(1.0, 3.0), (6.0, 8.0)] or result == [(1.0, 5.0), (6.0, 8.0)]
    # Correct: overlapping [1,3] and [2,5] should merge to [1,5]
    assert merge_intervals([(1.0, 3.0), (2.0, 5.0)]) == [(1.0, 5.0)]


def test_merge_no_overlap():
    intervals = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]
    assert merge_intervals(intervals) == intervals


def test_merge_empty():
    assert merge_intervals([]) == []


def test_total_duration():
    intervals = [(0.0, 5.0), (10.0, 15.0)]
    assert total_duration(intervals) == pytest.approx(10.0)


def test_find_violations_near():
    merged = [(1.0, 3.0), (5.0, 7.0), (10.0, 12.0)]
    result = find_violations_near(merged, 4.5, 6.0)
    assert (5.0, 7.0) in result
    assert (1.0, 3.0) not in result
