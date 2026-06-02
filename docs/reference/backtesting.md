# `backtesting` — API reference

Public API of the `backtesting` package. Engines and adapters are
intentionally **not** documented here: callers depend only on the
abstract types below. Engine selection is a string passed to
`BacktestConfig` / `BacktestJob.backends`; the dispatch happens inside.

See [Backtesting plan](../plan/backtesting.md) for the design rationale.

## Input contract

::: backtesting.CanonicalBars

::: backtesting.validate

::: backtesting.bars_to_canonical_bars

## Configuration

::: backtesting.BacktestConfig

::: backtesting.Tolerance

## Results

::: backtesting.BacktestResult

::: backtesting.ReconciliationReport

## Canonical-schema validators

::: backtesting.validate_fill_list

::: backtesting.validate_trade_list

::: backtesting.validate_equity_curve

## Errors

::: backtesting.BacktestError

::: backtesting.ValidationError

::: backtesting.UnsupportedFeatureError

::: backtesting.AdapterError

::: backtesting.ReconciliationError

::: backtesting.BacktestNotRunError

::: backtesting.BacktestFailedError

::: backtesting.AlreadyRanError
