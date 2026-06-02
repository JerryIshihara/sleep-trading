"""Strategy contract.

The ``Strategy`` ABC defines what a strategy must be in order to be runnable —
by the backtest engine, by live execution, by any consumer. Strategies emit
discrete position targets per bar; the consumer is responsible for turning
those into fills under its own execution model.

The ``BarFrame`` Protocol pins what a strategy can read from its bars input
without naming the concrete class. ``src/backtesting/``'s ``CanonicalBars``
satisfies this Protocol structurally; the live-mode equivalent will too.
This is the no-cycle seam: strategy code never imports backtest types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

import pandas as pd

PositionTarget = Literal[-1, 0, 1]
"""Discrete exposure target: -1 short, 0 flat, +1 long. 0 is an explicit
flat target, never a no-op / hold signal."""


@runtime_checkable
class BarFrame(Protocol):
    """Anything a Strategy can read its bars from.

    Both ``CanonicalBars`` (backtest input) and the eventual live-mode
    equivalent satisfy this. Strategy code never imports the concrete
    class — duck typing carries the contract.
    """

    symbol: str
    venue: str
    interval: str
    frame: pd.DataFrame  # tz-aware UTC DatetimeIndex, OHLCV float64 columns


@dataclass(frozen=True)
class ExitRules:
    """Declarative exit overrides layered on top of target-position logic.

    All four fields are optional. The engine enforces them as the consumer
    sees fit (capability-gated per adapter). Strategies set these once;
    they are not modified per-bar.
    """

    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_stop_pct: float | None = None
    max_bars_held: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("stop_loss_pct", self.stop_loss_pct),
            ("take_profit_pct", self.take_profit_pct),
            ("trailing_stop_pct", self.trailing_stop_pct),
        ):
            if value is not None and not (0 < value < 1):
                raise ValueError(
                    f"ExitRules.{name} must be in (0, 1); got {value!r}"
                )
        if self.max_bars_held is not None and self.max_bars_held < 1:
            raise ValueError(
                f"ExitRules.max_bars_held must be >= 1; got {self.max_bars_held!r}"
            )


class Strategy(ABC):
    """Target-position strategy.

    Implementations return one discrete ``PositionTarget`` per input bar.

    Causality rule: the target at bar ``t`` may depend only on bars through
    ``t``. Consumers enforce this via prefix-invariance tests:
        ``targets(bars[:t+1]) == targets(bars)[:t+1]``
    A vectorized implementation that quietly references future rows fails
    this test before any engine runs.

    The fill timing rule (target at ``t`` fills at ``t+1`` open) belongs to
    the consumer, not the strategy. Strategies emit intent; consumers
    execute it.
    """

    name: str
    warmup_bars: int = 0
    exits: ExitRules | None = None

    @abstractmethod
    def generate_targets(self, bars: BarFrame) -> pd.Series:
        """Return one PositionTarget per bar in ``bars.frame``.

        Returned Series:

        - index identical to ``bars.frame.index`` (same length, same
          timestamps, same tz)
        - dtype numeric and losslessly coercible to ``int8``
        - values exactly in ``{-1, 0, +1}``
        - NaN permitted only in the first ``self.warmup_bars`` positions
        """
