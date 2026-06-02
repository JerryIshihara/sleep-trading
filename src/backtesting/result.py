"""Per-engine ``BacktestResult`` and cross-engine ``ReconciliationReport``.

The fill list, trade list, and equity curve are the canonical artifacts
every adapter must return. Headline scalars (Sharpe, Sortino, ...) are
recomputed by ``backtest.metrics`` from those artifacts — never trusted
from the underlying engine.

This module also exports validators for the three canonical frame shapes so
adapter tests can pin the schema without depending on engine machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from backtesting.errors import ValidationError

# ─── Canonical schemas ─────────────────────────────────────────────


FILL_COLUMNS: dict[str, str] = {
    "ts": "datetime64[ns, UTC]",
    "side": "string",
    "qty": "float64",
    "px": "float64",
    "fee": "float64",
    "reason": "string",
    "order_group_id": "int64",
}

TRADE_COLUMNS: dict[str, str] = {
    "entry_ts": "datetime64[ns, UTC]",
    "exit_ts": "datetime64[ns, UTC]",
    "side": "string",
    "entry_px": "float64",
    "exit_px": "float64",
    "size": "float64",
    "pnl": "float64",
    "return_pct": "float64",
    "bars_held": "int64",
    "exit_reason": "string",
}

VALID_FILL_SIDES: frozenset[str] = frozenset({"buy", "sell"})
VALID_TRADE_SIDES: frozenset[str] = frozenset({"long", "short"})
VALID_EXIT_REASONS: frozenset[str] = frozenset({
    "target_change",
    "stop_loss",
    "take_profit",
    "trailing_stop",
    "max_bars_held",
    "end_of_data",
})


# ─── BacktestResult ────────────────────────────────────────────────


@dataclass(frozen=True)
class BacktestResult:
    """Normalized output of one adapter run.

    The three canonical frames (``equity_curve``, ``fill_list``,
    ``trade_list``) are the primitive artifacts. Scalar metrics are
    recomputed by :mod:`backtest.metrics` from those frames so that
    cross-engine differences reflect real divergence and not different
    conventions (e.g. trading-days-per-year).

    ``raw_metrics`` is a per-engine debug-only escape hatch and is never
    consumed by the reconciler.
    """

    backend: str

    # Headline scalars (recomputed from canonical frames; engines do not fill these)
    total_return: float
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    max_drawdown_duration: pd.Timedelta
    win_rate: float
    profit_factor: float
    exposure_pct: float

    # Canonical frames
    equity_curve: pd.Series
    fill_list: pd.DataFrame
    trade_list: pd.DataFrame

    # Debugging escape hatch
    raw_metrics: dict[str, Any] = field(default_factory=dict)


# ─── ReconciliationReport ──────────────────────────────────────────


Verdict = Literal["pass", "warn", "fail"]
Fidelity = Literal["full", "degraded", "reduced"]


@dataclass(frozen=True)
class ReconciliationReport:
    """Cross-engine diff output.

    ``per_backend`` may include failed adapter runs as ``None`` so callers
    can see who failed without the report being silently incomplete.
    """

    per_backend: dict[str, BacktestResult | None]
    verdict: Verdict
    fidelity: Fidelity
    metric_diffs: pd.DataFrame
    equity_max_rel_dev: float
    mismatched_fills: pd.DataFrame
    notes: tuple[str, ...] = ()


# ─── Validators (pure functions, exported for tests + adapter use) ─


def validate_fill_list(fills: pd.DataFrame) -> None:
    """Validate the canonical fill list shape.

    Empty frames are permitted (a strategy may not trade) provided columns
    and dtypes still match.
    """
    _require_columns(fills, FILL_COLUMNS, label="fill_list")
    _require_dtypes(fills, FILL_COLUMNS, label="fill_list")
    if len(fills) == 0:
        return
    bad_side = ~fills["side"].isin(VALID_FILL_SIDES)
    if bad_side.any():
        raise ValidationError(
            f"fill_list.side has values outside {sorted(VALID_FILL_SIDES)}"
        )
    if (fills["qty"] <= 0).any():
        raise ValidationError("fill_list.qty must be strictly positive")
    if (fills["px"] <= 0).any():
        raise ValidationError("fill_list.px must be strictly positive")
    if (fills["fee"] < 0).any():
        raise ValidationError("fill_list.fee must be >= 0")
    bad_reason = ~fills["reason"].isin(VALID_EXIT_REASONS)
    if bad_reason.any():
        raise ValidationError(
            f"fill_list.reason has values outside {sorted(VALID_EXIT_REASONS)}"
        )
    if not fills["ts"].is_monotonic_increasing:
        raise ValidationError("fill_list must be sorted by ts ascending")


def validate_trade_list(trades: pd.DataFrame) -> None:
    """Validate the canonical trade list shape.

    In v1 every trade is closed (open positions get a synthetic
    ``end_of_data`` exit), so ``exit_ts`` and ``exit_px`` are non-null.
    """
    _require_columns(trades, TRADE_COLUMNS, label="trade_list")
    _require_dtypes(trades, TRADE_COLUMNS, label="trade_list")
    if len(trades) == 0:
        return
    bad_side = ~trades["side"].isin(VALID_TRADE_SIDES)
    if bad_side.any():
        raise ValidationError(
            f"trade_list.side has values outside {sorted(VALID_TRADE_SIDES)}"
        )
    if trades["entry_ts"].isna().any():
        raise ValidationError("trade_list.entry_ts must not contain NaT")
    if trades["exit_ts"].isna().any():
        raise ValidationError(
            "trade_list.exit_ts must not contain NaT (v1 force-closes open trades)"
        )
    if (trades["exit_ts"] < trades["entry_ts"]).any():
        raise ValidationError("trade_list.exit_ts must be >= entry_ts for every row")
    if (trades["size"] <= 0).any():
        raise ValidationError("trade_list.size must be strictly positive")
    if (trades["bars_held"] < 0).any():
        raise ValidationError("trade_list.bars_held must be >= 0")
    bad_reason = ~trades["exit_reason"].isin(VALID_EXIT_REASONS)
    if bad_reason.any():
        raise ValidationError(
            f"trade_list.exit_reason has values outside {sorted(VALID_EXIT_REASONS)}"
        )
    if not trades["entry_ts"].is_monotonic_increasing:
        raise ValidationError("trade_list must be sorted by entry_ts ascending")


def validate_equity_curve(equity: pd.Series, *, expected_index: pd.Index) -> None:
    """Validate the canonical equity curve.

    ``expected_index`` should match the input bars frame index — alignment
    is mandatory so the reconciler can compare curves pointwise.
    """
    if not isinstance(equity, pd.Series):
        raise ValidationError(
            f"equity_curve must be pd.Series, got {type(equity).__name__}"
        )
    if equity.dtype != np.float64:
        raise ValidationError(
            f"equity_curve dtype must be float64, got {equity.dtype}"
        )
    if len(equity) != len(expected_index):
        raise ValidationError(
            f"equity_curve length ({len(equity)}) must match bars index ({len(expected_index)})"
        )
    if not equity.index.equals(expected_index):
        raise ValidationError("equity_curve index must match bars index exactly")
    if equity.isna().any():
        raise ValidationError("equity_curve must not contain NaN")
    arr = equity.to_numpy()
    if np.isinf(arr).any():
        raise ValidationError("equity_curve must not contain +/-inf")
    if (arr < 0).any():
        raise ValidationError("equity_curve must not contain negative values")


# ─── Internal helpers ──────────────────────────────────────────────


def _require_columns(
    df: pd.DataFrame, expected: dict[str, str], *, label: str
) -> None:
    if not isinstance(df, pd.DataFrame):
        raise ValidationError(f"{label} must be pd.DataFrame, got {type(df).__name__}")
    actual = list(df.columns)
    if actual != list(expected.keys()):
        raise ValidationError(
            f"{label} columns must be exactly {list(expected.keys())}, got {actual}"
        )


def _require_dtypes(
    df: pd.DataFrame, expected: dict[str, str], *, label: str
) -> None:
    for col, dtype_str in expected.items():
        actual = df[col].dtype
        if dtype_str.startswith("datetime64"):
            # Accept any tz-aware UTC datetime resolution (pandas 2.x defaults
            # constructors to microsecond precision; engine outputs may vary).
            if not isinstance(actual, pd.DatetimeTZDtype) or str(actual.tz) != "UTC":
                raise ValidationError(
                    f"{label}.{col} must be a tz-aware UTC datetime dtype, got {actual!r}"
                )
        elif dtype_str == "string":
            # pandas' StringDtype repr varies by storage backend; check via API.
            if not isinstance(actual, pd.StringDtype):
                raise ValidationError(
                    f"{label}.{col} dtype must be pandas StringDtype, got {actual!r}"
                )
        elif str(actual) != dtype_str:
            raise ValidationError(
                f"{label}.{col} dtype must be {dtype_str!r}, got {actual!r}"
            )


__all__ = [
    "FILL_COLUMNS",
    "TRADE_COLUMNS",
    "VALID_EXIT_REASONS",
    "VALID_FILL_SIDES",
    "VALID_TRADE_SIDES",
    "BacktestResult",
    "Fidelity",
    "ReconciliationReport",
    "Verdict",
    "validate_equity_curve",
    "validate_fill_list",
    "validate_trade_list",
]
