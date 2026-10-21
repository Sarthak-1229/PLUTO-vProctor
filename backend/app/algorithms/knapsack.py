"""0/1 Knapsack (dynamic programming) for interview time budget allocation.

Used to select the best combination of questions that fit within a fixed interview time,
maximising relevance/difficulty score while respecting per-question time estimates.

Time:  O(N * W) where N = number of questions, W = time budget (integer seconds)
Space: O(N * W) full table; O(W) with rolling-row optimisation
"""
from __future__ import annotations
from typing import List, NamedTuple


class KnapsackItem(NamedTuple):
    """Represents one candidate interview question for the knapsack."""
    id: int              # Unique question identifier
    weight: int          # Estimated answering time in seconds (integer)
    value: float         # Relevance / importance score


def knapsack_01(items: List[KnapsackItem], capacity: int) -> tuple[float, List[int]]:
    """Solve the 0/1 knapsack problem and return selected item IDs.

    Uses a space-optimised DP approach with a 1-D rolling array.

    Args:
        items:    List of KnapsackItem objects (id, weight, value).
        capacity: Total time budget in integer seconds.

    Returns:
        Tuple of (total_value, selected_ids) where selected_ids are question IDs.

    Time:  O(N * W)
    Space: O(W)
    """
    n = len(items)
    if n == 0 or capacity <= 0:
        return 0.0, []

    # dp[w] = max value achievable with time budget w
    dp = [0.0] * (capacity + 1)
    # keep[i][w] = True if item i is included when budget = w
    keep = [[False] * (capacity + 1) for _ in range(n)]

    for i, item in enumerate(items):
        # Traverse backwards to prevent using same item twice
        for w in range(capacity, item.weight - 1, -1):
            candidate = dp[w - item.weight] + item.value
            if candidate > dp[w]:
                dp[w] = candidate
                keep[i][w] = True

    # Backtrack to find selected items
    selected_ids: List[int] = []
    w = capacity
    for i in range(n - 1, -1, -1):
        if keep[i][w]:
            selected_ids.append(items[i].id)
            w -= items[i].weight

    return dp[capacity], list(reversed(selected_ids))
