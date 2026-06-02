"""Validators for BacktestResult's canonical frames."""

from __future__ import annotations

from datetime import UTC

import numpy as np
import pandas as pd
import pytest

from backtesting import (
    ValidationError,
    validate_equity_curve,
    validate_fill_list,
    validate_trade_list,
)
from backtesting.result import FILL_COLUMNS, TRADE_COLUMNS

_FILL_STRING_COLS = ("side", "reason")
_TRADE_STRING_COLS = ("side", "exit_reason")


def _empty_fill_list() -> pd.DataFrame:
    df = pd.DataFrame({col: pd.Series([], dtype=dtype) for col, dtype in FILL_COLUMNS.items()})
    return df


def _empty_trade_list() -> pd.DataFrame:
    df = pd.DataFrame({col: pd.Series([], dtype=dtype) for col, dtype in TRADE_COLUMNS.items()})
    return df


def _row_fill(*, ts, side, qty, px, fee, reason, order_group_id=0) -> pd.DataFrame:
    """Build a one-row fill_list with dtypes preserved.

    pandas' ``.loc[i] = [...]`` downcasts StringDtype to object; explicit
    re-cast restores the canonical schema.
    """
    df = _empty_fill_list()
    df.loc[0] = [ts, side, qty, px, fee, reason, order_group_id]
    return df.astype({col: "string" for col in _FILL_STRING_COLS})


def _row_trade(
    *, entry_ts, exit_ts, side, entry_px, exit_px, size, pnl, return_pct, bars_held, exit_reason
) -> pd.DataFrame:
    df = _empty_trade_list()
    df.loc[0] = [entry_ts, exit_ts, side, entry_px, exit_px, size, pnl, return_pct, bars_held, exit_reason]
    return df.astype({col: "string" for col in _TRADE_STRING_COLS})


class TestValidateFillList:
    def test_empty_passes(self) -> None:
        validate_fill_list(_empty_fill_list())

    def test_missing_column_rejected(self) -> None:
        bad = _empty_fill_list().drop(columns=["fee"])
        with pytest.raises(ValidationError, match="fill_list columns"):
            validate_fill_list(bad)

    def test_invalid_side_rejected(self) -> None:
        df = _row_fill(
            ts=pd.Timestamp("2024-01-01", tz="UTC"),
            side="long",  # invalid; must be buy/sell
            qty=1.0, px=100.0, fee=0.0, reason="target_change",
        )
        with pytest.raises(ValidationError, match=r"fill_list\.side has values"):
            validate_fill_list(df)

    def test_nonpositive_qty_rejected(self) -> None:
        df = _row_fill(
            ts=pd.Timestamp("2024-01-01", tz="UTC"),
            side="buy",
            qty=0.0, px=100.0, fee=0.0, reason="target_change",
        )
        with pytest.raises(ValidationError, match="qty"):
            validate_fill_list(df)

    def test_invalid_reason_rejected(self) -> None:
        df = _row_fill(
            ts=pd.Timestamp("2024-01-01", tz="UTC"),
            side="buy",
            qty=1.0, px=100.0, fee=0.0, reason="bogus",
        )
        with pytest.raises(ValidationError, match=r"fill_list\.reason has values"):
            validate_fill_list(df)


class TestValidateTradeList:
    def test_empty_passes(self) -> None:
        validate_trade_list(_empty_trade_list())

    def test_invalid_side_rejected(self) -> None:
        df = _row_trade(
            entry_ts=pd.Timestamp("2024-01-01", tz="UTC"),
            exit_ts=pd.Timestamp("2024-01-02", tz="UTC"),
            side="buy",  # must be long/short
            entry_px=100.0, exit_px=101.0, size=1.0, pnl=1.0, return_pct=0.01,
            bars_held=1, exit_reason="target_change",
        )
        with pytest.raises(ValidationError, match=r"trade_list\.side has values"):
            validate_trade_list(df)

    def test_exit_before_entry_rejected(self) -> None:
        df = _row_trade(
            entry_ts=pd.Timestamp("2024-01-02", tz="UTC"),
            exit_ts=pd.Timestamp("2024-01-01", tz="UTC"),  # exit before entry
            side="long",
            entry_px=100.0, exit_px=101.0, size=1.0, pnl=1.0, return_pct=0.01,
            bars_held=1, exit_reason="target_change",
        )
        with pytest.raises(ValidationError, match="exit_ts must be >= entry_ts"):
            validate_trade_list(df)


class TestValidateEquityCurve:
    def test_happy_path(self) -> None:
        idx = pd.date_range("2024-01-01", periods=10, freq="1min", tz=UTC)
        equity = pd.Series(np.linspace(100_000.0, 100_100.0, 10), index=idx, dtype=np.float64)
        validate_equity_curve(equity, expected_index=idx)

    def test_not_series_rejected(self) -> None:
        idx = pd.date_range("2024-01-01", periods=3, freq="1min", tz=UTC)
        with pytest.raises(ValidationError, match=r"must be pd\.Series"):
            validate_equity_curve([100.0, 100.0, 100.0], expected_index=idx)  # type: ignore[arg-type]

    def test_wrong_dtype_rejected(self) -> None:
        idx = pd.date_range("2024-01-01", periods=3, freq="1min", tz=UTC)
        equity = pd.Series([100, 101, 102], index=idx)  # int64
        with pytest.raises(ValidationError, match="dtype"):
            validate_equity_curve(equity, expected_index=idx)

    def test_index_mismatch_rejected(self) -> None:
        idx_a = pd.date_range("2024-01-01", periods=3, freq="1min", tz=UTC)
        idx_b = pd.date_range("2024-02-01", periods=3, freq="1min", tz=UTC)
        equity = pd.Series([100.0, 101.0, 102.0], index=idx_a, dtype=np.float64)
        with pytest.raises(ValidationError, match="index"):
            validate_equity_curve(equity, expected_index=idx_b)

    def test_negative_rejected(self) -> None:
        idx = pd.date_range("2024-01-01", periods=3, freq="1min", tz=UTC)
        equity = pd.Series([100.0, -1.0, 102.0], index=idx, dtype=np.float64)
        with pytest.raises(ValidationError, match="negative"):
            validate_equity_curve(equity, expected_index=idx)
