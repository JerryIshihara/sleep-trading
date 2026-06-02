"""Smoke test: every public name in the package imports cleanly."""

from __future__ import annotations


def test_public_api_imports() -> None:
    import backtesting

    expected = {
        "CanonicalBars",
        "bars_to_canonical_bars",
        "validate",
        "BacktestConfig",
        "Tolerance",
        "BacktestResult",
        "ReconciliationReport",
        "validate_fill_list",
        "validate_trade_list",
        "validate_equity_curve",
        "BacktestError",
        "ValidationError",
        "UnsupportedFeatureError",
        "AdapterError",
        "ReconciliationError",
        "BacktestNotRunError",
        "BacktestFailedError",
        "AlreadyRanError",
    }
    missing = expected - set(dir(backtesting))
    assert not missing, f"missing from public API: {sorted(missing)}"


def test_error_hierarchy() -> None:
    from backtesting import (
        AdapterError,
        AlreadyRanError,
        BacktestError,
        BacktestFailedError,
        BacktestNotRunError,
        ReconciliationError,
        UnsupportedFeatureError,
        ValidationError,
    )

    for cls in (
        ValidationError,
        UnsupportedFeatureError,
        AdapterError,
        ReconciliationError,
        BacktestNotRunError,
        BacktestFailedError,
        AlreadyRanError,
    ):
        assert issubclass(cls, BacktestError), f"{cls.__name__} is not a BacktestError"


def test_strategy_protocol_imports() -> None:
    """`strategy` is a separate sibling package and must be importable
    independently of backtest."""
    import strategy

    assert hasattr(strategy, "Strategy")
    assert hasattr(strategy, "ExitRules")
    assert hasattr(strategy, "PositionTarget")
    assert hasattr(strategy, "BarFrame")
