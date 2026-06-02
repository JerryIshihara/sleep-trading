"""Sleep Trading — unified backtesting engine.

Public API surface. Internals (validators, per-engine adapters, sinks) live
under their respective modules but are re-exported here when they form part
of the user-facing contract.

See ``docs/plan/backtesting.md`` for design intent.
"""

from backtesting.bars import CanonicalBars, bars_to_canonical_bars, validate
from backtesting.config import BacktestConfig, Tolerance
from backtesting.errors import (
    AdapterError,
    AlreadyRanError,
    BacktestError,
    BacktestFailedError,
    BacktestNotRunError,
    ReconciliationError,
    UnsupportedFeatureError,
    ValidationError,
)
from backtesting.result import (
    BacktestResult,
    ReconciliationReport,
    validate_equity_curve,
    validate_fill_list,
    validate_trade_list,
)

__all__ = [
    "AdapterError",
    "AlreadyRanError",
    "BacktestConfig",
    "BacktestError",
    "BacktestFailedError",
    "BacktestNotRunError",
    "BacktestResult",
    "CanonicalBars",
    "ReconciliationError",
    "ReconciliationReport",
    "Tolerance",
    "UnsupportedFeatureError",
    "ValidationError",
    "bars_to_canonical_bars",
    "validate",
    "validate_equity_curve",
    "validate_fill_list",
    "validate_trade_list",
]
