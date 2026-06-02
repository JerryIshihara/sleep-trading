"""Backtest configuration and reconciliation tolerances.

Both ``BacktestConfig`` and ``Tolerance`` are frozen dataclasses — pass them
to ``Backtest.from_strategy(...)`` once; the engine never mutates them.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from backtesting.errors import ValidationError

FillPolicy = Literal["next_open"]
PositionSizing = Literal["full_notional"]


@dataclass(frozen=True)
class BacktestConfig:
    """Per-run configuration.

    v1 ships exactly one ``fill_policy`` and one ``position_sizing``. Both
    fields are kept on the dataclass so v2's expansion is purely additive.
    """

    initial_cash: Decimal
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    fill_policy: FillPolicy = "next_open"
    position_sizing: PositionSizing = "full_notional"
    allow_short: bool = True

    def __post_init__(self) -> None:
        # Runtime check defends against callers ignoring the static signature.
        if not isinstance(self.initial_cash, Decimal):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValidationError(
                f"initial_cash must be Decimal, got {type(self.initial_cash).__name__}"
            )
        if self.initial_cash <= 0:
            raise ValidationError(f"initial_cash must be > 0, got {self.initial_cash}")
        if self.commission_bps < 0:
            raise ValidationError(f"commission_bps must be >= 0, got {self.commission_bps}")
        if self.slippage_bps < 0:
            raise ValidationError(f"slippage_bps must be >= 0, got {self.slippage_bps}")


@dataclass(frozen=True)
class Tolerance:
    """Per-metric reconciliation thresholds.

    A diff exceeding any threshold marks the metric as ``fail``. The verdict
    aggregates across all metrics. Defaults are calibrated for daily-bar
    strategies with realistic costs; tighten for high-frequency, loosen for
    monthly-rebalance.
    """

    total_return_bps: float = 50.0
    sharpe_abs: float = 0.15
    max_drawdown_bps: float = 50.0
    equity_curve_max_rel_dev: float = 0.005
    fill_count_must_match_exactly: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("total_return_bps", self.total_return_bps),
            ("sharpe_abs", self.sharpe_abs),
            ("max_drawdown_bps", self.max_drawdown_bps),
            ("equity_curve_max_rel_dev", self.equity_curve_max_rel_dev),
        ):
            if value < 0:
                raise ValidationError(f"Tolerance.{name} must be >= 0, got {value}")


__all__ = [
    "BacktestConfig",
    "FillPolicy",
    "PositionSizing",
    "Tolerance",
]
