# plans

Living implementation plans for major components. Each file captures context, goals, abstractions, and the execution path for one subsystem. Plans are updated in place as the design evolves.

- [`dashboard.md`](./dashboard.md) — web UI under `src/dashboard/` (Vite + React).
- [`data.md`](./data.md) — data layer abstractions (events, sources, sinks, client); skeleton lives at `src/data/`.
- [`backtesting.md`](./backtesting.md) — unified backtest engine wrapping VectorBT / Backtesting.py / Backtrader for cross-checking; lands at `src/backtest/`. Covers v1 (signal-only) and v2 (event-driven, walk-forward, ReplayAdapter integration).

When a plan and the code disagree, the plan is the *intent* and the code is the *current state*. Only update a plan if the intent has actually shifted — code drift alone shouldn't rewrite a plan.
