# Multi-Engine Backtest Wrappers — Survey

Companion to [`survey.md`](./survey.md). That file maps the landscape of individual backtest engines (VectorBT, Backtrader, Backtesting.py, Zipline, Nautilus, LEAN). This file answers a narrower question: **does anyone already wrap multiple engines under one unified Strategy API for cross-checking, and if so, how do they design that API?** It feeds [`../../plan/backtesting.md`](../../plan/backtesting.md).

## Headline finding

**No open-source Python package wraps multiple major backtest engines under one unified strategy API for cross-checking.** The closest candidates either (a) deploy native-engine code to live brokers, (b) wrap a single engine more deeply, or (c) standardize *metrics* without standardizing the strategy interface. The market gap that motivates `src/backtest/` is real.

## Existing wrappers — what they actually do

### StrateQueue
[GitHub](https://github.com/StrateQueue/StrateQueue) · active.

Supports VectorBT, Backtrader, Backtesting.py, Zipline-Reloaded, and `bt`. **But it does not unify the Strategy API.** Users write strategies in each engine's native form; StrateQueue deploys that native code to live brokers (Alpaca, IB, CCXT) via a single CLI command. The cross-engine support is at the deployment layer, not the strategy authorship layer. Signal-only mode by default to prevent accidental live trading.

Implication for us: validates that the engines are bridgeable to a common runtime, but doesn't solve the cross-check problem.

### NautilusTrader
[GitHub](https://github.com/nautechsystems/nautilus_trader) · active, professional-grade (Rust core, Python bindings).

Multi-venue, event-driven, nanosecond-tick simulation — but it is a single engine, its own. Not a multi-engine wrapper. Its hexagonal-architecture "ports and adapters" abstract over **venues** (exchanges, broker APIs), not over backtest engines.

### Lumibot
[GitHub](https://github.com/Lumiwealth/lumibot) · active.

Multi-broker strategy framework: same `Strategy` subclass runs against Alpaca, IBKR, Tradier, Polygon, etc. — but the *backtest* engine is Lumibot's own event-driven implementation. Brokers are pluggable; engines are not.

### `bt`, `finmarketpy`, `moonshot`, `open-backtest`
All single-engine. `bt` (pmorissette) uses an algo-composition tree, finmarketpy is Cuemacro's macro/seasonality library, moonshot is QuantRocket's vectorized pandas engine, open-backtest targets Binance crypto. None wrap external engines.

### Backtesting.py `lib.MultiBacktest`
Parallelizes one strategy across multiple **instruments** in the same engine — not a multi-engine cross-check.

### gs-quant (Goldman Sachs)
[Developer docs](https://developer.gs.com/docs/gsquant/) reference a "cross-asset backtesting language compatible with a variety of calculation engines", but the public documentation contains no API surface and no list of supported engines. Closed or heavily restricted.

### Verdict

| Feature | Available off-the-shelf? |
|---|---|
| One Strategy class, runs on Backtrader + VectorBT + Backtesting.py | **No** |
| Normalized metric schema across engines | Partial — QuantStats handles metrics, but only post-hoc |
| Reconciliation / diff across engine results | **No** |
| Deployment of native-engine code to live brokers | Yes — StrateQueue |

## Strategy abstraction patterns in major frameworks

What the field has converged on, looking at seven frameworks individually:

| Framework | Per-bar surface | Order surface | Live/backtest swap |
|---|---|---|---|
| **QuantConnect LEAN** | `OnData(Slice)` callback | `SetHoldings`, `Order`, fills via `OnOrderEvent` | Engine swaps data source at runtime; code unchanged |
| **NautilusTrader** | `on_bar`, `on_quote_tick`, `on_trade_tick` callbacks | `submit_order()` async via MessageBus | Same Strategy code; backtest replays data deterministically |
| **Lumibot** | `on_trading_iteration()` per bar (backtest) or minute (live) | `submit_order()` synchronous | Inject `Broker` at startup (`Backtest(...)` vs `Live(broker=Alpaca(...))`) |
| **Backtrader** | `next()` per bar | `buy()` / `sell()`; `notify_order()` callback | `cerebro` swaps `Broker` + `DataFeed` instances |
| **Zipline-Reloaded** | `handle_data(context, data)` | `order()`, `order_target()`; portfolio updates in-loop | Backtest only; data via "bundle" system |
| **VectorBT(Pro)** | Vectorized signal arrays *or* `order_func_nb` callback | Implicit via signal arrays | Vectorized only — no live mode |
| **Hummingbot** | `on_tick()` | `create_order(connector, order)`; `OrderCompletedEvent` callback | Connector swap at startup; same StrategyBase |

### The intersection API

Every event-driven framework on this list reduces to the same four operations:

1. **`initialize(config)`** — set up state, subscribe to instruments.
2. **`on_bar(bar) -> list[Order]`** — receive one bar, return zero or more orders.
3. **`on_order_filled(fill)`** — react to a fill (optional in most).
4. **Live ↔ backtest swap by dependency injection** at startup. Strategy code unchanged.

VectorBT is the consistent outlier: its native API is vectorized (signal arrays), not callback-driven. A unified wrapper either (a) restricts the API to a vectorizable subset (signals only), (b) translates `on_bar` into a slow Python loop wrapping VectorBT, or (c) makes VectorBT optional.

This is precisely the v1-vs-v2 split in [`../../plan/backtesting.md`](../../plan/backtesting.md): v1 is signal-only (the largest subset all three engines express natively); v2 adds an `EventStrategy` `on_bar` API that runs on Backtesting.py + Backtrader but skips VectorBT with a warning.

## Cross-engine divergence — what people who tried have found

A small body of practitioner reports documents what happens when the same strategy is run through multiple engines. The single most consistent finding: **with zero transaction costs and aligned data, engines agree to numerical precision; divergence is driven almost entirely by cost/fill modeling.**

### "Implementation Risk in Portfolio Backtesting" (academic, citation needs verification — agent-supplied arXiv URL appears malformed)
- Five engines, four strategy types (simple allocation, ML signals, low-turnover rotation, high-turnover rotation).
- Simple strategies: 0.18–0.75% return divergence across engines.
- ML + medium turnover: 0.27–0.49% divergence.
- High-turnover rotation: **3.71% divergence** (~$37M/yr on $1B AUM).
- **Zero-cost configurations: 0.00% divergence** — proves cost modeling is the sole driver.

### SMA crossover, VectorBT vs Backtrader
[jiahau3 on Medium](https://jiahau3.medium.com/building-a-trend-following-strategy-and-comparing-with-backtrader-and-vectorbt-563c64fbbc76). VectorBT matched a pandas manual computation to the dollar. Backtrader diverged because of stricter cash-management realism — at the requested trade size, Backtrader judged there wasn't enough cash to execute identically. Reconciliation required adjusting the sizing assumption, not the strategy.

### Asset-class structural effects
["One Backtesting Framework Is Never Enough"](https://medium.com/@tierdrop06/one-backtesting-framework-is-never-enough-b608a2d69ce4) — same strategy, same framework, different asset class → divergence. Small-cap slippage variance, crypto fee structure differences, futures roll handling. Lesson: framework divergence is secondary to market-structure assumption divergence.

### Ranked sources of divergence (across all reports surveyed)

1. **Commission timing** — when commission is charged (entry, exit, or linearly) drives 40–100% per-trade variance in extreme cases. One framework's default was off by 100× from another's.
2. **Fill price assumption** — open vs. close vs. midpoint. Shifts effective signal by one bar.
3. **Slippage model** — fixed bps vs. percentage vs. market-impact curve. 0.1–2% return drag.
4. **Position sizing realism** — fractional shares, lot rounding, cash-availability checks. 5–15% trade-count divergence.
5. **Dividend / split treatment** — 1–5% return divergence on multi-year holds.
6. **Off-by-one signal shifts** — fire-on-current-bar vs. fire-on-next-bar.
7. **NaN / gap handling** — weekends, halts, partial fills.

## Implications for `src/backtest/`

What this survey changes (or doesn't) in [`../../plan/backtesting.md`](../../plan/backtesting.md):

1. **The market-gap premise holds.** Building a multi-engine cross-checker is not duplicating an existing package — there isn't one. StrateQueue is the closest and solves a different problem.
2. **The v1 signal-only Strategy API matches the intersection.** All three target engines (VectorBT, Backtesting.py, Backtrader) natively express signal arrays; that's the largest common denominator.
3. **The v2 `EventStrategy` shape aligns with the field.** `initialize` + `on_bar` + optional `on_order_filled` is what LEAN, Nautilus, Lumibot, Backtrader, and Hummingbot have all converged on. Keep the shape.
4. **The reconciler's failure-mode taxonomy is the right one.** The ranked divergence sources above (commission timing, fill price, slippage, position sizing) are exactly what our per-metric tolerance thresholds + trade-list diff should surface. Worth mirroring the ranking inside `reconcile.py` docstrings as the "what divergence usually means" guide.
5. **A zero-cost baseline test is now non-negotiable.** The "zero cost → zero divergence" finding from the academic study is a stronger sanity test than buy-and-hold parity alone. Add a zero-commission, zero-slippage parity test alongside the existing `test_buy_and_hold_parity.py` — divergence there is a guaranteed adapter bug, not a strategy bug.
6. **Tolerance defaults from the plan look directionally right.** ±50 bps for total return / Sharpe ±0.15 lines up with the "simple strategies diverge 0.18–0.75% with realistic costs" finding. High-turnover strategies would need tighter or per-strategy tolerances — that's a v1 open question worth resolving with this data in hand.

## Sources

Verified during this survey:
- [StrateQueue GitHub](https://github.com/StrateQueue/StrateQueue)
- [NautilusTrader](https://nautilustrader.io/)
- [Lumibot](https://lumibot.lumiwealth.com/)
- [Backtrader Strategy docs](https://www.backtrader.com/docu/strategy/)
- [Zipline-Reloaded API reference](https://zipline.ml4trading.io/api-reference.html)
- [Hummingbot docs](https://hummingbot.org/docs/)
- [VectorBT discussion #209](https://github.com/polakowo/vectorbt/discussions/209)
- [Building a Trend-Following Strategy: VectorBT vs Backtrader — jiahau3 on Medium](https://jiahau3.medium.com/building-a-trend-following-strategy-and-comparing-with-backtrader-and-vectorbt-563c64fbbc76)
- [One Backtesting Framework Is Never Enough — Medium](https://medium.com/@tierdrop06/one-backtesting-framework-is-never-enough-b608a2d69ce4)
- [Battle-Tested Backtesters — Trading Dude on Medium](https://medium.com/@trading.dude/battle-tested-backtesters-comparing-vectorbt-zipline-and-backtrader-for-financial-strategy-dee33d33a9e0)

Citations that came up but need verification before being used as authoritative:
- "Implementation Risk in Portfolio Backtesting" — agent-supplied arXiv URL was malformed (year 2603). The directional findings (zero-cost → zero divergence; high-turnover up to 3.7%) are plausible and consistent with the practitioner reports, but treat numeric magnitudes as illustrative until the real paper is located.
- Goldman Sachs gs-quant claims of "multi-engine compatibility" — public docs show no API surface or engine list; could not confirm what it actually does.
