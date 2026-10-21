"""Interval merging for overlapping proctoring violation segments and experience ranges.

Time:  O(N log N) due to sorting
Space: O(N)
"""
from __future__ import annotations
from typing import List, Tuple

Interval = Tuple[float, float]


def merge_intervals(intervals: List[Interval]) -> List[Interval]:
    """Merge overlapping intervals.

    Args:
        intervals: List of (start, end) float tuples (e.g. seconds).
                   Input may be unsorted.

    Returns:
        List of non-overlapping merged (start, end) tuples sorted by start.

    Time:  O(N log N)
    Space: O(N)
    """
    if not intervals:
        return []
    sorted_ivs = sorted(intervals, key=lambda iv: iv[0])
    merged: List[Interval] = [sorted_ivs[0]]

    for start, end in sorted_ivs[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def total_duration(intervals: List[Interval]) -> float:
    """Sum the total duration covered by the (already merged) intervals.

    Args:
        intervals: List of non-overlapping (start, end) tuples.

    Returns:
        Total seconds covered.
    """
    return sum(end - start for start, end in intervals)


def find_violations_near(
    merged: List[Interval],
    query_start: float,
    query_end: float,
) -> List[Interval]:
    """Return all merged intervals that overlap [query_start, query_end].

    Useful for extracting violation segments near a specific video timestamp window.

    Args:
        merged: List of non-overlapping sorted intervals.
        query_start: Start of the query window.
        query_end:   End of the query window.

    Returns:
        List of overlapping intervals.
    """
    return [
        iv for iv in merged
        if iv[0] < query_end and iv[1] > query_start
    ]
