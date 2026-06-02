"""BacktestConfig and Tolerance validation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backtesting import BacktestConfig, Tolerance, ValidationError


class TestBacktestConfig:
    def test_defaults_with_required_field(self) -> None:
        cfg = BacktestConfig(initial_cash=Decimal("100_000"))
        assert cfg.commission_bps == 0.0
        assert cfg.slippage_bps == 0.0
        assert cfg.fill_policy == "next_open"
        assert cfg.position_sizing == "full_notional"
        assert cfg.allow_short is True

    def test_initial_cash_must_be_decimal(self) -> None:
        with pytest.raises(ValidationError, match="initial_cash must be Decimal"):
            BacktestConfig(initial_cash=100_000)  # type: ignore[arg-type]

    def test_initial_cash_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match="initial_cash must be > 0"):
            BacktestConfig(initial_cash=Decimal("0"))

    def test_commission_must_be_nonnegative(self) -> None:
        with pytest.raises(ValidationError, match="commission_bps must be >= 0"):
            BacktestConfig(initial_cash=Decimal("1"), commission_bps=-1.0)

    def test_slippage_must_be_nonnegative(self) -> None:
        with pytest.raises(ValidationError, match="slippage_bps must be >= 0"):
            BacktestConfig(initial_cash=Decimal("1"), slippage_bps=-1.0)

    def test_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        cfg = BacktestConfig(initial_cash=Decimal("1"))
        with pytest.raises(FrozenInstanceError):
            cfg.commission_bps = 5.0  # type: ignore[misc]


class TestTolerance:
    def test_defaults(self) -> None:
        tol = Tolerance()
        assert tol.total_return_bps == 50.0
        assert tol.sharpe_abs == 0.15
        assert tol.max_drawdown_bps == 50.0
        assert tol.equity_curve_max_rel_dev == 0.005
        assert tol.fill_count_must_match_exactly is True

    def test_negative_values_rejected(self) -> None:
        with pytest.raises(ValidationError, match="total_return_bps"):
            Tolerance(total_return_bps=-1.0)
        with pytest.raises(ValidationError, match="sharpe_abs"):
            Tolerance(sharpe_abs=-0.01)
