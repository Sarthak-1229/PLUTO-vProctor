"""Tests for 0/1 Knapsack DP."""
import pytest
from backend.app.algorithms.knapsack import KnapsackItem, knapsack_01


def test_basic_knapsack():
    items = [
        KnapsackItem(id=1, weight=2, value=6),
        KnapsackItem(id=2, weight=2, value=10),
        KnapsackItem(id=3, weight=3, value=12),
    ]
    value, selected = knapsack_01(items, capacity=5)
    assert value == pytest.approx(22.0)
    assert set(selected) == {2, 3}


def test_knapsack_zero_capacity():
    items = [KnapsackItem(id=1, weight=2, value=5)]
    value, selected = knapsack_01(items, capacity=0)
    assert value == 0.0
    assert selected == []


def test_knapsack_empty():
    assert knapsack_01([], 100) == (0.0, [])


def test_knapsack_all_fit():
    items = [
        KnapsackItem(id=i, weight=1, value=float(i))
        for i in range(1, 6)
    ]
    value, selected = knapsack_01(items, capacity=5)
    assert set(selected) == {1, 2, 3, 4, 5}
    assert value == pytest.approx(15.0)
