"""CanonicalBars validator and Bar → CanonicalBars conversion."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backtesting import CanonicalBars, ValidationError, bars_to_canonical_bars, validate


class TestValidate:
    def test_happy_path(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bars = validate(synthetic_ramp_frame, symbol="AAPL", venue="NASDAQ", interval="1m")
        assert isinstance(bars, CanonicalBars)
        assert bars.symbol == "AAPL"
        assert bars.venue == "NASDAQ"
        assert bars.interval == "1m"
        assert list(bars.frame.columns) == ["open", "high", "low", "close", "volume"]
        assert bars.frame.index.tz is not None

    def test_empty_symbol_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        with pytest.raises(ValidationError, match="symbol must be a non-empty string"):
            validate(synthetic_ramp_frame, symbol="", venue="NASDAQ", interval="1m")

    def test_unknown_interval_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        with pytest.raises(ValidationError, match="interval must be one of"):
            validate(synthetic_ramp_frame, symbol="AAPL", venue="NASDAQ", interval="7m")

    def test_non_dataframe_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"frame must be pd\.DataFrame"):
            validate({"open": [1.0]}, symbol="AAPL", venue="NASDAQ", interval="1m")  # type: ignore[arg-type]

    def test_missing_column_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.drop(columns=["volume"])
        with pytest.raises(ValidationError, match=r"missing \['volume'\]"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_extra_column_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.assign(extra=1.0)
        with pytest.raises(ValidationError, match=r"extra \['extra'\]"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_naive_index_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.copy()
        bad.index = bad.index.tz_localize(None)
        with pytest.raises(ValidationError, match="tz-aware"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_non_utc_index_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.copy()
        bad.index = bad.index.tz_convert("America/New_York")
        with pytest.raises(ValidationError, match="UTC"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_non_monotonic_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.copy()
        # swap two consecutive timestamps
        idx = list(bad.index)
        idx[5], idx[6] = idx[6], idx[5]
        bad.index = pd.DatetimeIndex(idx)
        with pytest.raises(ValidationError, match="monotonic"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_duplicate_timestamps_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.copy()
        idx = list(bad.index)
        idx[1] = idx[0]
        bad.index = pd.DatetimeIndex(idx)
        with pytest.raises(ValidationError, match="unique timestamps"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_non_datetime_index_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.reset_index(drop=True)
        with pytest.raises(ValidationError, match="DatetimeIndex"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_nan_in_close_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.copy()
        bad.loc[bad.index[0], "close"] = np.nan
        with pytest.raises(ValidationError, match="NaN"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_inf_in_open_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.copy()
        bad.loc[bad.index[0], "open"] = np.inf
        with pytest.raises(ValidationError, match="inf"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_negative_volume_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.copy()
        bad.loc[bad.index[0], "volume"] = -1.0
        with pytest.raises(ValidationError, match="negative"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_nan_volume_coerced_to_zero(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.copy()
        bad.loc[bad.index[0], "volume"] = np.nan
        bars = validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")
        assert bars.frame["volume"].iloc[0] == 0.0

    def test_high_below_close_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.copy()
        bad.loc[bad.index[10], "high"] = bad.loc[bad.index[10], "close"] - 1.0
        with pytest.raises(ValidationError, match="high"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_low_above_open_rejected(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        bad = synthetic_ramp_frame.copy()
        bad.loc[bad.index[10], "low"] = bad.loc[bad.index[10], "open"] + 1.0
        with pytest.raises(ValidationError, match="low"):
            validate(bad, symbol="AAPL", venue="NASDAQ", interval="1m")

    def test_canonical_column_order(self, synthetic_ramp_frame: pd.DataFrame) -> None:
        shuffled = synthetic_ramp_frame[["volume", "close", "low", "high", "open"]]
        bars = validate(shuffled, symbol="AAPL", venue="NASDAQ", interval="1m")
        assert list(bars.frame.columns) == ["open", "high", "low", "close", "volume"]


class TestBarsToCanonicalBars:
    def _make_bar(self, ts_open: datetime, *, symbol: str = "AAPL", venue: str = "NASDAQ", interval: str = "1m"):
        from data.events import Bar

        return Bar(
            symbol=symbol,
            venue=venue,
            ts_open=ts_open,
            ts_close=ts_open,
            interval=interval,  # type: ignore[arg-type]
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100.5"),
            volume=Decimal("1000"),
        )

    def test_happy_path(self) -> None:
        bars = [
            self._make_bar(datetime(2024, 1, 1, tzinfo=UTC)),
            self._make_bar(datetime(2024, 1, 1, 0, 1, tzinfo=UTC)),
            self._make_bar(datetime(2024, 1, 1, 0, 2, tzinfo=UTC)),
        ]
        result = bars_to_canonical_bars(bars)
        assert result.symbol == "AAPL"
        assert result.venue == "NASDAQ"
        assert result.interval == "1m"
        assert len(result.frame) == 3

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            bars_to_canonical_bars([])

    def test_mixed_symbol_rejected(self) -> None:
        bars = [
            self._make_bar(datetime(2024, 1, 1, tzinfo=UTC), symbol="AAPL"),
            self._make_bar(datetime(2024, 1, 1, 0, 1, tzinfo=UTC), symbol="MSFT"),
        ]
        with pytest.raises(ValidationError, match="mixed symbol"):
            bars_to_canonical_bars(bars)

    def test_mixed_venue_rejected(self) -> None:
        bars = [
            self._make_bar(datetime(2024, 1, 1, tzinfo=UTC), venue="NASDAQ"),
            self._make_bar(datetime(2024, 1, 1, 0, 1, tzinfo=UTC), venue="NYSE"),
        ]
        with pytest.raises(ValidationError, match="mixed venue"):
            bars_to_canonical_bars(bars)
