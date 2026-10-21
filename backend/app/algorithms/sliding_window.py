"""Sliding window statistics with EMA and simple Kalman-like smoothing.

Used for:
- Detecting look-away events using a sliding window over gaze samples.
- Estimating head motion level from pose landmarks.
- Smoothing noisy per-frame proctoring signals into a stable metric.

Sliding window:
    Time:  O(1) per update (amortised)
    Space: O(W) where W = window size

EMA update:
    Time / Space: O(1)
"""
from __future__ import annotations
from collections import deque
from typing import Deque, List, Optional


class SlidingWindowStats:
    """Fixed-size sliding window computing running mean and variance.

    Attributes:
        window_size: Maximum number of samples in the window.
    """

    def __init__(self, window_size: int) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be >= 1")
        self.window_size = window_size
        self._buffer: Deque[float] = deque(maxlen=window_size)
        self._sum: float = 0.0
        self._sum_sq: float = 0.0

    def push(self, value: float) -> None:
        """Add a new sample, evicting the oldest if at capacity.

        Args:
            value: New measurement.
        """
        if len(self._buffer) == self.window_size:
            old = self._buffer[0]
            self._sum -= old
            self._sum_sq -= old * old
        self._buffer.append(value)
        self._sum += value
        self._sum_sq += value * value

    def mean(self) -> float:
        """Return the current window mean. Returns 0.0 if no data."""
        n = len(self._buffer)
        return self._sum / n if n else 0.0

    def variance(self) -> float:
        """Return population variance of the window. Returns 0.0 if < 2 samples."""
        n = len(self._buffer)
        if n < 2:
            return 0.0
        return max(0.0, self._sum_sq / n - (self._sum / n) ** 2)

    def __len__(self) -> int:
        return len(self._buffer)


class EMAFilter:
    """Exponential Moving Average filter for sensor smoothing.

    Attributes:
        alpha: Smoothing factor in (0, 1]. Higher alpha = more weight on new values.
    """

    def __init__(self, alpha: float = 0.2) -> None:
        if not (0 < alpha <= 1):
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self._value: Optional[float] = None

    def update(self, measurement: float) -> float:
        """Update EMA with a new measurement and return the smoothed value.

        Args:
            measurement: New raw sensor reading.

        Returns:
            Smoothed EMA value.
        """
        if self._value is None:
            self._value = measurement
        else:
            self._value = self.alpha * measurement + (1 - self.alpha) * self._value
        return self._value

    @property
    def value(self) -> Optional[float]:
        """Current EMA value (None if no measurements yet)."""
        return self._value

    def reset(self) -> None:
        """Reset the filter state."""
        self._value = None


class SimpleKalmanFilter:
    """One-dimensional scalar Kalman filter for proctoring signal smoothing.

    Models a scalar state with process noise Q and measurement noise R.
    Useful for smoothing gaze deviation or head motion signals.

    Attributes:
        Q: Process noise covariance. Higher = more responsive to rapid changes.
        R: Measurement noise covariance. Higher = more smoothing.
    """

    def __init__(self, Q: float = 1e-3, R: float = 0.1, initial_estimate: float = 0.0) -> None:
        self.Q = Q
        self.R = R
        self._x = initial_estimate  # State estimate
        self._p = 1.0               # Estimate covariance

    def update(self, measurement: float) -> float:
        """Predict + update Kalman step.

        Args:
            measurement: New noisy observation.

        Returns:
            Kalman-filtered (smoothed) state estimate.
        """
        # Predict
        p_pred = self._p + self.Q
        # Kalman gain
        K = p_pred / (p_pred + self.R)
        # Update
        self._x = self._x + K * (measurement - self._x)
        self._p = (1 - K) * p_pred
        return self._x

    @property
    def estimate(self) -> float:
        """Current state estimate."""
        return self._x
