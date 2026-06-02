# src

Source code root. **`src/` is the project root** for the Python side: it
holds the single `pyproject.toml`, the shared `.venv`, and the four
sibling modules below. Per-module pyprojects are intentionally absent —
one project, several packages.

## Modules

- **`data/`** — market-data event types, vendor adapters (planned), replay, storage. Imported as `data`.
- **`strategy/`** — strategy contract (`Strategy` ABC, `ExitRules`, `BarFrame` Protocol) and authoring. Imported as `strategy`. Has no dependency on `backtesting/`.
- **`backtesting/`** — unified backtest engine wrapping VectorBT, Backtesting.py, and Backtrader for cross-checking. Imported as `backtesting`.
- **`dashboard/`** — TypeScript / React / Vite frontend. Independent of the Python tree.

## Install (Python side)

```bash
cd src
python3.11 -m venv .venv          # 3.11+ required
.venv/bin/python -m pip install -e ".[dev]"
```

Add engine extras as needed:

```bash
.venv/bin/python -m pip install -e ".[dev,vectorbt,backtesting_py,backtrader]"
# or all three at once:
.venv/bin/python -m pip install -e ".[dev,all_engines]"
```

## Run tests

```bash
.venv/bin/pytest backtesting/tests/
```

## Lint + type-check

```bash
.venv/bin/ruff check .
.venv/bin/basedpyright
```

## Dependency direction (must hold)

```
data        ◄── strategy  (optional, only if event-driven strategies need Bar)
   ▲              ▲
   │              │
   └─── backtesting  (imports Bar from data; imports Strategy / BarFrame
                      / ExitRules from strategy)

strategy  never imports from  backtesting  ←── the rule that matters
```
