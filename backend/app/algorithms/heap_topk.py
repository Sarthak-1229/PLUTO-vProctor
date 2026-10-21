"""Binary min-heap (Top-K selection) hand-implementation.

Used to pick the top-K most relevant interview questions for a session.

Time complexity:
    heappush: O(log K)
    heappop:  O(log K)
    top_k:    O(N log K) where N = number of items

Space complexity: O(K) for the heap buffer
"""
from __future__ import annotations
from typing import Any, Generic, List, Optional, Tuple, TypeVar

T = TypeVar("T")


class MinHeap(Generic[T]):
    """Generic binary min-heap for comparable elements.

    Elements must support the < operator.
    For top-K by a score key, use (score, item) tuples.
    """

    def __init__(self) -> None:
        self._data: List[T] = []

    def __len__(self) -> int:
        return len(self._data)

    def peek(self) -> Optional[T]:
        """Return the minimum element without removing it."""
        return self._data[0] if self._data else None

    def push(self, item: T) -> None:
        """Insert item into the heap. O(log N)."""
        self._data.append(item)
        self._sift_up(len(self._data) - 1)

    def pop(self) -> T:
        """Remove and return the minimum element. O(log N).

        Raises:
            IndexError: If the heap is empty.
        """
        if not self._data:
            raise IndexError("pop from empty heap")
        self._data[0], self._data[-1] = self._data[-1], self._data[0]
        item = self._data.pop()
        if self._data:
            self._sift_down(0)
        return item

    def _sift_up(self, idx: int) -> None:
        while idx > 0:
            parent = (idx - 1) // 2
            if self._data[idx] < self._data[parent]:
                self._data[idx], self._data[parent] = self._data[parent], self._data[idx]
                idx = parent
            else:
                break

    def _sift_down(self, idx: int) -> None:
        n = len(self._data)
        while True:
            smallest = idx
            left = 2 * idx + 1
            right = 2 * idx + 2
            if left < n and self._data[left] < self._data[smallest]:
                smallest = left
            if right < n and self._data[right] < self._data[smallest]:
                smallest = right
            if smallest == idx:
                break
            self._data[idx], self._data[smallest] = self._data[smallest], self._data[idx]
            idx = smallest


def top_k(items: List[Tuple[float, Any]], k: int) -> List[Tuple[float, Any]]:
    """Return the K items with the highest scores using a min-heap of size K.

    Args:
        items: List of (score, item) tuples. Higher score = more relevant.
        k: Number of top items to return.

    Returns:
        List of up to K (score, item) tuples sorted by score descending.

    Time:  O(N log K)
    Space: O(K)
    """
    if k <= 0:
        return []
    heap: MinHeap[Tuple[float, Any]] = MinHeap()
    for score, item in items:
        heap.push((score, item))
        if len(heap) > k:
            heap.pop()
    result = []
    while heap:
        result.append(heap.pop())
    return sorted(result, key=lambda x: x[0], reverse=True)
