"""Tests for sliding window, EMA, and Kalman filter."""
import pytest
from backend.app.algorithms.sliding_window import SlidingWindowStats, EMAFilter, SimpleKalmanFilter


def test_sliding_window_mean():
    sw = SlidingWindowStats(window_size=3)
    sw.push(1.0)
    sw.push(2.0)
    sw.push(3.0)
    assert sw.mean() == pytest.approx(2.0)


def test_sliding_window_eviction():
    sw = SlidingWindowStats(window_size=2)
    sw.push(10.0)
    sw.push(20.0)
    sw.push(30.0)  # 10.0 evicted
    assert sw.mean() == pytest.approx(25.0)


def test_sliding_window_variance():
    sw = SlidingWindowStats(window_size=4)
    for v in [2.0, 4.0, 4.0, 4.0]:
        sw.push(v)
    assert sw.variance() >= 0.0


def test_ema_basic():
    ema = EMAFilter(alpha=1.0)  # alpha=1 => no smoothing, output = input
    assert ema.update(5.0) == pytest.approx(5.0)
    assert ema.update(10.0) == pytest.approx(10.0)


def test_ema_smoothing():
    ema = EMAFilter(alpha=0.1)
    ema.update(100.0)
    val = ema.update(0.0)
    assert 0.0 < val < 100.0  # Smoothed between old and new


def test_ema_reset():
    ema = EMAFilter()
    ema.update(50.0)
    ema.reset()
    assert ema.value is None


def test_kalman_basic():
    kf = SimpleKalmanFilter(Q=1e-3, R=0.1)
    estimates = [kf.update(float(i)) for i in range(10)]
    # Kalman output should smoothly follow input
    assert all(0 <= e <= 12 for e in estimates)


def test_kalman_convergence():
    kf = SimpleKalmanFilter()
    for _ in range(100):
        kf.update(5.0)
    assert kf.estimate == pytest.approx(5.0, abs=0.01)
