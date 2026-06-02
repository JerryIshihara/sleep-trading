# Backtesting

Unified backtesting engine. One `Strategy` definition runs through
**VectorBT**, **Backtesting.py**, and **Backtrader** in parallel via
adapters; the reconciler flags inter-engine disagreement. Cross-checking is
the whole point — disagreement is evidence of bugs in strategy logic,
look-ahead, or engine-specific quirks.

See [`../../docs/plan/backtesting.md`](../../docs/plan/backtesting.md) for
the design.

## Layout

One module under `src/` (sibling to `data/`, `strategy/`, `dashboard/`).
`src/` is the project root and holds the single `pyproject.toml` — this
directory is a Python package, not its own project.

```
src/backtesting/             ← importable as `backtesting`
├── README.md
├── __init__.py              ← public API surface
├── errors.py
├── config.py
├── bars.py
├── result.py
├── engines/
│   └── backtesting_py/      ← adapter for the PyPI `backtesting` library
└── tests/
```

The package name `backtesting` shadows the PyPI library `backtesting.py`,
which we also wrap as one engine. The `engines/backtesting_py/adapter.py`
loads the PyPI library via `importlib.util.spec_from_file_location` from
its installed path on disk, sidestepping the import-shadowing issue. No
other code in this package touches the PyPI library directly.

## Quickstart

```python
from backtesting import Backtest, BacktestConfig
from strategy.strategies.sma_crossover import SmaCrossover

backtest = Backtest.from_strategy(
    SmaCrossover(fast=10, slow=30),
    bars=load_parquet("data.parquet"),
    config=BacktestConfig(initial_cash=Decimal("100_000")),
)
report = backtest.run()
```

## Install engine extras

From `src/`:

```bash
.venv/bin/python -m pip install -e ".[vectorbt,backtesting_py,backtrader]"
# or
.venv/bin/python -m pip install -e ".[all_engines]"
```

## License caveat

The PyPI `backtesting` library is AGPL-3.0. Fine for personal research; if
this code is ever shipped as a hosted service, the `backtesting_py` engine
needs to be optional — install `[vectorbt,backtrader]` instead of
`[all_engines]`.
