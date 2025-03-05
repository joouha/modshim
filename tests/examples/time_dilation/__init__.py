"""Enhanced time module with time dilation capability."""

from __future__ import annotations

import time as original_time

# Time dilation factor (1.0 = normal time, 2.0 = twice as fast, 0.5 = half speed)
_dilation_factor = 1.0
_base_time = original_time.time()
_base_real_time = original_time.time()


def set_dilation(factor: float) -> None:
    """Set the time dilation factor."""
    global _dilation_factor, _base_time, _base_real_time
    _base_time = time()  # Current dilated time
    _base_real_time = original_time.time()  # Current real time
    _dilation_factor = factor


def time() -> float:
    """Return dilated time in seconds since the epoch."""
    real_elapsed = original_time.time() - _base_real_time
    dilated_elapsed = real_elapsed * _dilation_factor
    return _base_time + dilated_elapsed


def sleep(seconds: float) -> None:
    """Sleep for the given number of dilated seconds."""
    if seconds <= 0:
        return
    real_seconds = seconds / _dilation_factor
    original_time.sleep(real_seconds)
