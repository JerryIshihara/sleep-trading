"""Shared test fixtures.

Synthetic OHLCV frames cover the three common shapes used across the test
suite: linear ramp (sanity baseline), sine overlay (signals fire), and a
gap with NaN warmup region.
"""

from __future__ import annotations

from datetime import UTC

import numpy as np
import pandas as pd
import pytest


def _utc_index(n: int, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start=start, periods=n, freq="1min", tz=UTC)


@pytest.fixture
def synthetic_ramp_frame() -> pd.DataFrame:
    """1000-bar linear price ramp. Close goes from 100 to 110 monotonically."""
    n = 1000
    idx = _utc_index(n)
    close = np.linspace(100.0, 110.0, n)
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.maximum(open_, close) + 0.05
    low = np.minimum(open_, close) - 0.05
    volume = np.full(n, 1_000.0)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


@pytest.fixture
def synthetic_sine_frame() -> pd.DataFrame:
    """1000-bar sine overlay around 100. Useful for SMA-crossover style tests."""
    n = 1000
    idx = _utc_index(n)
    base = 100.0 + 5.0 * np.sin(np.linspace(0, 10 * np.pi, n))
    close = base
    open_ = np.concatenate([[base[0]], base[:-1]])
    high = np.maximum(open_, close) + 0.10
    low = np.minimum(open_, close) - 0.10
    volume = np.full(n, 1_000.0)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )
