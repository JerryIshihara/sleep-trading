# Backtesting Frameworks: Approaches, Tools, and Design Patterns

## Summary

Backtesting is how you validate a trading idea without risking real capital. Two paradigms dominate: vectorized (fast, for research) and event-driven (realistic, for validation). Vectorized engines (VectorBT, NumPy) process entire years of data in seconds by pushing loops into compiled code. Event-driven engines (Backtrader, Zipline, Nautilus) simulate trading one bar or tick at a time, mimicking live conditions. Most small teams use vectorized for quick parameter sweeps, then event-driven for detailed validation before live trading. This survey covers both paradigms, major open-source engines, and pitfalls (look-ahead bias, slippage, overfitting).

## Vectorized Backtesting (Fast, Research-Grade)

### VectorBT
- **Language:** Python (NumPy, Numba).
- **Speed:** 10,000+ strategies in seconds (on modern CPU).
- **Output:** Metrics (Sharpe, max drawdown, returns) as arrays; no visual trades.
- **Slippage modeling:** Simple (fixed spread).
- **Installation:** `pip install vectorbt`.
- **Use case:** Parameter sweeps, portfolio-level research, walk-forward analysis.
- **Learning curve:** Medium (need NumPy/Numba comfort).
- **Best for:** Quant researchers optimizing signal parameters.

### Zipline-Reloaded
- **Language:** Python.
- **Speed:** Hours for large backtests (bar-by-bar loop).
- **Niche:** Long/short equity factor strategies (Quantopian legacy).
- **Output:** Tearsheets, exposures, risk factor attribution.
- **Installation:** `pip install zipline-reloaded` (requires Pandas compatibility).
- **Use case:** Academic factor research.
- **Learning curve:** High (foreign API; data setup painful).
- **Status:** Community-maintained; stable but slow-moving.

### Polars + Pandas
- **DIY approach:** Write custom backtest logic using Polars (fast) or Pandas.
- **Advantage:** Full control; no framework assumptions.
- **Disadvantage:** More boilerplate.
- **Use case:** Simple strategies, quick prototyping.

---

## Event-Driven Backtesting (Realistic, Production-Grade)

### Backtrader
- **Language:** Python.
- **Speed:** Minutes to hours (bar-by-bar loop with hooks).
- **Realism:** High (order types, slippage, commission modeling, position holding).
- **Output:** P&L, trades, order logs.
- **Installation:** `pip install backtrader`.
- **Live trading:** Direct integration (Alpaca, IBKR, etc.).
- **Use case:** Swing trading, intraday, crypto; production-ready strategies.
- **Learning curve:** Medium.
- **Community:** Large; many examples.
- **Best for:** Retail traders going live soon.

### Backtesting.py
- **Language:** Python.
- **Speed:** Minutes (bar-by-bar, simpler than Backtrader).
- **Ease of use:** High (clean API; learning in minutes).
- **Output:** Returns, Sharpe, drawdown.
- **Installation:** `pip install backtesting`.
- **Use case:** Quick validation, educational, simple strategies.
- **Learning curve:** Low.
- **Limitation:** No live trading integration.
- **Best for:** Quick strategy idea validation.

### Nautilus Trader
- **Language:** Rust (Python bindings).
- **Speed:** Fast event-driven (Rust performance).
- **Realism:** Highest (production-grade risk, slippage, multi-venue).
- **Output:** Detailed metrics, trade logs.
- **Installation:** Complex (requires Rust build).
- **Live trading:** Yes (multiple brokers).
- **Use case:** Professional quant shops, high-frequency strategies.
- **Learning curve:** High.
- **Status:** Active, well-funded.
- **Best for:** Teams deploying multi-million dollar strategies.

### PyAlgoTrade
- **Language:** Python.
- **Speed:** Slow (event-driven, pure Python).
- **Realism:** Medium (basic order types).
- **Output:** Trade stats, P&L.
- **Installation:** `pip install pyalgotrade`.
- **Use case:** Educational, legacy code base.
- **Learning curve:** Medium.
- **Status:** Dormant (last commit 2017).

---

## Cloud / Managed Platforms

### QuantConnect LEAN
- **Language:** C# + Python bindings.
- **Speed:** Cloud backtesting (fast due to server resources).
- **Realism:** High (institutional-grade slippage, commission, spreads).
- **Coverage:** 20+ data sources, 20+ brokers.
- **Output:** Metrics, risk reports, live trading integration.
- **Cost:** Free (limited) → $99+/month (pro).
- **Use case:** Multi-asset portfolios; institutional-grade.
- **Learning curve:** Medium.
- **Community:** Large; good docs.
- **Best for:** Teams needing cloud infrastructure; risk-averse backtesting.

---

## Key Design Patterns

### Walk-Forward Analysis
Process:
1. Split history into windows (e.g., 1-year train, 6-month test, rolling forward weekly).
2. Optimize parameters on training window.
3. Test on test window (out-of-sample).
4. Repeat; average results.

**Why:** Detects overfitting. A strategy that works on in-sample but fails out-of-sample is overfitted.

**Tools:** VectorBT, Zipline, QuantConnect all support this.

### Avoiding Look-Ahead Bias
**Golden rule:** Only use data available at time t to generate signal at time t.

**Mistakes:**
- Using close(t) to decide whether to buy at open(t). ❌ (You don't know close yet.)
- Using tomorrow's news to trade today. ❌
- Aggregating weekly OHLC bars using future data. ❌

**Fix:** Strict data cutoff. Pass only [0:t-1] to feature calculation; generate signal at t; execute at t+1 open.

### Slippage & Commission Modeling
- **Slippage:** Difference between requested price and fill price. Model as fixed (e.g., 1 tick) or percentage (e.g., 0.05%).
- **Commission:** Per-share (equities) or per-contract (futures).
- **Spread:** Bid-ask difference; order fills at mid + 1/2 spread on average.

**Example:**
```python
# backtrader
data.close[0] * (1 - 0.001)  # 0.1% slippage on exit
```

**Tools:** Backtrader, Nautilus, QuantConnect all allow configurable slippage.

---

## Workflow Recommendation for Small Teams

```
1. Idea (notebook, rough signal)
   ↓
2. Vectorized backtest (VectorBT)
   - Quick sweep 100 parameter combos in 10 seconds
   - Check Sharpe, max drawdown, win rate
   ↓
3. Event-driven backtest (Backtrader or Backtesting.py)
   - Repeat best combos from step 2
   - Realistic slippage, commission, order types
   - Walk-forward validation
   ↓
4. Paper trading (Alpaca, IBKR, Binance testnet)
   - Same code as live
   - Real API latency
   - Real market conditions (not simulated)
   ↓
5. Live trading (1% of capital, single symbol)
   - Validate slippage, fill rates
   - Monitor daily
   ↓
6. Scale (if profitable after 2 weeks)
```

---

## Architectural Takeaways for sleep-trading

1. **Vectorized for discovery.** VectorBT finds the needle (profitable parameter set) in the haystack (all possible parameters).

2. **Event-driven for validation.** Backtrader confirms the needle still works when slippage and commission are real.

3. **Walk-forward kills false positives.** If a strategy "works" in-sample but fails out-of-sample, reject it.

4. **Slippage is not optional.** Most retail strategies fail live because slippage wasn't modeled. Assume 1 tick minimum.

5. **Never backtest on future data.** Use strict data cutoffs. Many open-source repos have this bug; audit carefully.

6. **Paper trade is not live.** Paper fills are instant and perfect. Real fills slip and take time. Paper P&L is 20–50% optimistic.

7. **Separate research and live backtest.** Keep two code paths: one for Jupyter (VectorBT), one for prod (Backtrader + live code path).

## Sources

- [Comparing VectorBT, Zipline, and Backtrader - Medium](https://medium.com/@trading.dude/battle-tested-backtesters-comparing-vectorbt-zipline-and-backtrader-for-financial-strategy-dee33d33a9e0)
- [Backtesting landscape 2026 - python.financial](https://python.financial/)
- [Walk-forward analysis - Interactive Brokers](https://www.interactivebrokers.com/campus/ibkr-quant-news/the-future-of-backtesting-a-deep-dive-into-walk-forward-analysis/)
- [Look-ahead bias prevention - Surmount](https://surmount.ai/blogs/walk-forward-analysis-vs-backtesting-pros-cons-and-best-practices)
- [Vectorbt efficiency vs event-driven - GitHub discussion](https://github.com/polakowo/vectorbt/discussions/185)
