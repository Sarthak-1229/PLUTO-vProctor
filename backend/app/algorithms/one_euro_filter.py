"""1€ (One Euro) adaptive low-pass filter for real-time human motion & gaze tracking.

Reference:
    Casiez, G., Roussel, N., & Vogel, D. (2012).
    1€ filter: a simple speed-based low-pass filter for noisy input in interactive systems.
    Proceedings of the SIGCHI Conference on Human Factors in Computing Systems, 2527-2530.

Provides:
    - Jitter reduction at low speeds (steady eye fixation).
    - Near-zero lag during rapid saccades or head rotations.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple, Union


class LowPassFilter:
    """Standard exponential smoothing low-pass filter."""

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.y: Optional[float] = None
        self.s: Optional[float] = None

    def filter(self, value: float, alpha: Optional[float] = None) -> float:
        if alpha is not None:
            self.alpha = alpha
        if self.y is None:
            self.s = value
        else:
            self.s = self.alpha * value + (1.0 - self.alpha) * self.s
        self.y = value
        return self.s

    def last_value(self) -> Optional[float]:
        return self.s

    def reset(self):
        self.y = None
        self.s = None


class OneEuroFilter:
    """1€ adaptive filter for a single scalar value."""

    def __init__(
        self,
        t0: float = 0.0,
        x0: float = 0.0,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ):
        """Initialize the One Euro Filter.

        Args:
            t0: Initial timestamp (seconds).
            x0: Initial value.
            min_cutoff: Minimum cutoff frequency in Hz (> 0). Decreasing min_cutoff reduces jitter.
            beta: Speed coefficient (> 0). Increasing beta reduces lag during fast movements.
            d_cutoff: Cutoff frequency for derivative filter in Hz.
        """
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)

        self.x_filt = LowPassFilter()
        self.dx_filt = LowPassFilter()
        self.t_prev = float(t0)
        self.x_filt.filter(x0)
        self.initialized = False

    @staticmethod
    def _alpha(rate: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te = 1.0 / max(1e-6, rate)
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float, timestamp: Optional[float] = None) -> float:
        """Filter a new incoming sample x at timestamp (in seconds)."""
        if not self.initialized:
            self.initialized = True
            self.t_prev = timestamp if timestamp is not None else 0.0
            return self.x_filt.filter(x)

        if timestamp is not None and timestamp > self.t_prev:
            te = timestamp - self.t_prev
            self.t_prev = timestamp
        else:
            te = 1.0 / 30.0  # default 30 FPS estimate if timestamp not monotonic

        rate = 1.0 / te if te > 0 else 30.0

        # Estimate derivative (speed of change)
        prev_x = self.x_filt.last_value()
        dx = (x - prev_x) * rate if prev_x is not None else 0.0
        edx = self.dx_filt.filter(dx, self._alpha(rate, self.d_cutoff))

        # Compute adaptive cutoff frequency
        cutoff = self.min_cutoff + self.beta * abs(edx)

        # Filter signal with adaptive cutoff
        return self.x_filt.filter(x, self._alpha(rate, cutoff))

    def reset(self):
        self.x_filt.reset()
        self.dx_filt.reset()
        self.initialized = False


class OneEuroFilterVector:
    """1€ adaptive filter for N-dimensional coordinates or angles (e.g. [yaw, pitch, roll])."""

    def __init__(
        self,
        dim: int,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ):
        self.dim = dim
        self.filters = [
            OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)
            for _ in range(dim)
        ]

    def filter(self, values: List[float], timestamp: Optional[float] = None) -> List[float]:
        if len(values) != self.dim:
            raise ValueError(f"Expected {self.dim} values, got {len(values)}")
        return [
            f.filter(val, timestamp)
            for f, val in zip(self.filters, values)
        ]

    def reset(self):
        for f in self.filters:
            f.reset()
