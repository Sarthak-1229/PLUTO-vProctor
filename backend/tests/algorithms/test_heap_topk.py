"""Tests for MinHeap and top_k selection."""
import heapq
import pytest
from backend.app.algorithms.heap_topk import MinHeap, top_k


def test_min_heap_push_pop():
    h = MinHeap()
    for v in [5, 1, 3, 2, 4]:
        h.push(v)
    result = []
    while h:
        result.append(h.pop())
    assert result == [1, 2, 3, 4, 5]


def test_min_heap_matches_heapq():
    import random
    values = [random.randint(0, 100) for _ in range(50)]
    h = MinHeap()
    ref = []
    for v in values:
        h.push(v)
        heapq.heappush(ref, v)
    our_result = [h.pop() for _ in range(len(values))]
    ref_result = [heapq.heappop(ref) for _ in range(len(values))]
    assert our_result == ref_result


def test_top_k():
    items = [(score, f"q{i}") for i, score in enumerate([0.9, 0.1, 0.7, 0.5, 0.3])]
    result = top_k(items, k=3)
    scores = [s for s, _ in result]
    assert scores == sorted(scores, reverse=True)
    assert len(result) == 3
    assert result[0][0] == pytest.approx(0.9)


def test_top_k_fewer_than_k():
    items = [(0.5, "a"), (0.3, "b")]
    result = top_k(items, k=10)
    assert len(result) == 2


def test_top_k_empty():
    assert top_k([], k=5) == []
    assert top_k([(1.0, "x")], k=0) == []
