# Strategy Archetypes and Research Workflow

## Summary

Trading strategies fall into a few major classes: trend-following (buy strength, sell weakness), mean reversion (buy dips, sell rips), market making (profit from the spread), statistical arbitrage (exploit mispricings across correlated assets), and machine learning-based (learn patterns from data). Each archetype has different capital requirements, holding periods, and rebalancing frequencies. This survey catalogs archetype characteristics, research tools (Jupyter, Optuna, pyfolio), and the workflow from idea to paper trading. Small teams typically pick one archetype and master it deeply rather than chase every strategy.

## Strategy Archetypes

### Trend-Following (Momentum)
**Principle:** Markets have inertia. Strong recent performance tends to persist.

**Example signal:** 20-day return > 0 → buy; 20-day return < 0 → sell.

**Holding period:** Days to weeks.

**Capital efficiency:** High (leverage common).

**Pros:** Works in bull markets; intuitive; long/long-only possible.

**Cons:** Whipsaws in range-bound markets; crashes when trend reverses.

**Typical tool:** SMA/EMA crossovers; momentum oscillators (RSI, MACD).

**Small-team fit:** Easy to code and backtest. Good starter strategy.

---

### Mean Reversion
**Principle:** Prices oscillate around a mean. When far from the mean, revert.

**Example signal:** Price < SMA_20 - 2*STD → buy (oversold); Price > SMA_20 + 2*STD → sell (overbought).

**Holding period:** Hours to days (shorter than trend).

**Capital efficiency:** Medium.

**Pros:** Works in range-bound markets; risk/reward often asymmetric (quick wins, slow losses).

**Cons:** Loses money in strong trends (kept buying the dip in 2020 bull market).

**Typical tool:** Bollinger Bands, z-scores, RSI divergence.

**Small-team fit:** Simple to implement. Harder to make money (crowded).

---

### Market Making
**Principle:** Buy at bid, sell at ask; profit from the spread.

**Requirement:** Tight spreads, fast execution, multiple symbols.

**Holding period:** Seconds to minutes.

**Capital efficiency:** Very high (leverage often used).

**Pros:** Less directional risk (delta-neutral); consistent if you have edge.

**Cons:** Requires low latency (co-location); sophisticated order management; crowded.

**Typical tool:** Order book simulation; inventory management; signal based on bid-ask imbalance.

**Small-team fit:** Extremely hard for retail. Skip unless you have ≤10ms execution.

---

### Statistical Arbitrage (Stat Arb)
**Principle:** Exploit mean reversion in a portfolio of correlated assets.

**Example:** If Stock A and Stock B are highly correlated (0.95), but today A is up 5% and B is up 0%, expect B to catch up. Long B, short A.

**Holding period:** Days.

**Capital efficiency:** Medium.

**Pros:** Pairs-trading reduces systemic risk (beta-neutral).

**Cons:** Requires identifying and monitoring correlations; slippage kills returns.

**Typical tool:** Cointegration tests (Johansen), PCA, factor models.

**Small-team fit:** Good if you have domain knowledge (e.g., you know commodity relationships).

---

### Machine Learning-Based
**Principle:** Use ML to detect patterns in historical data and predict next-period returns.

**Approach:** 
1. Feature engineering (price, volume, volatility, sentiment, etc.).
2. Train supervised model (XGBoost, LSTM, etc.) to predict price direction.
3. Generate signals from model output.

**Holding period:** Variable.

**Pros:** Unlimited flexibility; can capture non-linear patterns.

**Cons:** Extremely prone to overfitting; data leakage (look-ahead bias); black box (hard to debug).

**Typical tool:** sklearn, XGBoost, PyTorch, TensorFlow.

**Small-team fit:** Risky without strong ML+data engineering background. Many failures. If attempting, focus on:
   - Walk-forward validation.
   - Explicit train/test split (no data leakage).
   - Feature importance (SHAP) to validate causality.

---

### Options Volatility
**Principle:** Volatility surface is often mispriced. Sell expensive vol, buy cheap vol.

**Example:** Sell iron condor when implied vol is high; expect vol to revert.

**Holding period:** Days to weeks.

**Pros:** Defined risk (short options); theta decay positive.

**Cons:** Requires options API (limited); Greeks management (delta, gamma, vega); large capital to manage risk.

**Small-team fit:** Skip unless you have options expertise. Only IBKR and Alpaca (limited) offer options APIs.

---

## Research Workflow: Idea to Live Trading

### Stage 1: Notebook Prototyping
Tool: Jupyter notebook.
```python
import pandas as pd
import numpy as np

# Load historical data
df = pd.read_csv('spy_daily.csv')
df['sma20'] = df['close'].rolling(20).mean()
df['signal'] = np.where(df['close'] < df['sma20'], 1, 0)  # buy signal

# Estimate returns (naive)
df['returns'] = df['close'].pct_change()
df['strategy_returns'] = df['signal'].shift(1) * df['returns']
df['cumulative_returns'] = (1 + df['strategy_returns']).cumprod()

print(f"Total return: {df['cumulative_returns'].iloc[-1] - 1:.2%}")
print(f"Sharpe ratio: {df['strategy_returns'].mean() / df['strategy_returns'].std() * np.sqrt(252):.2f}")
```

**Output:** Rough Sharpe ratio, max drawdown, intuition about strategy.

### Stage 2: Vectorized Backtest
Tool: VectorBT.
```python
import vectorbt as vbt

# Backtest 100 combinations: SMA window = 10..200, zscore threshold = 0.5..3.0
sma_windows = range(10, 210, 20)
zscores = np.arange(0.5, 3.0, 0.25)
results = vbt.Portfolio.from_signals(df, ...)  # vectorized over all combos
best_params = results.sortby('sharpe_ratio').iloc[-1]
```

**Output:** Best parameters found (SMA_window=50, zscore=1.5, Sharpe=0.8).

### Stage 3: Parameter Optimization
Tool: Optuna (hyperparameter optimization).
```python
import optuna

def objective(trial):
    sma_window = trial.suggest_int('sma_window', 10, 200)
    zscore_threshold = trial.suggest_float('zscore', 0.5, 3.0)
    
    # Run event-driven backtest with these params
    engine = BacktraderEngine(symbol='SPY', sma=sma_window, threshold=zscore_threshold)
    result = engine.run()
    return result['sharpe_ratio']

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=500)
best_params = study.best_params
```

**Output:** Optimized parameters; importance scores (which param matters most).

### Stage 4: Event-Driven Backtest (Walk-Forward)
Tool: Backtrader + walk-forward analysis.
```python
for train_start, train_end, test_start, test_end in walk_forward_splits:
    # Train on [train_start, train_end]
    best_params = optimize(data[train_start:train_end], ...)
    
    # Test on [test_start, test_end]
    results = backtest(data[test_start:test_end], best_params)
    results_log.append(results)

avg_sharpe = mean([r['sharpe'] for r in results_log])
print(f"Walk-forward Sharpe: {avg_sharpe:.2f}")
```

**Output:** Out-of-sample Sharpe (true estimate of live performance).

### Stage 5: Paper Trading
Tool: Alpaca, IBKR, or Binance testnet.
```python
# Same code as live, but with paper=True
from alpaca.trading.client import TradingClient

client = TradingClient(api_key, secret_key, paper=True)
order = client.submit_order(symbol='SPY', qty=100, side='buy', order_type='market')
```

**Duration:** 2 weeks minimum. Validate:
- API integration works.
- Fills match backtest assumptions.
- No fat-finger errors.
- Monitoring/alerting works.

### Stage 6: Live Trading (1% of Capital)
Tool: Live broker API.
```python
client = TradingClient(api_key, secret_key, paper=False)
# Same code; just different flag
```

**Duration:** 2 weeks. If profitable, scale to 5–10% of capital.

---

## Research Tools

### Jupyter + Pandas
Best for: Exploratory analysis, quick sketches.

### Optuna
For: Hyperparameter optimization. Handles discrete and continuous params; pruning; visualization.
```python
study = optuna.create_study()
study.optimize(objective, n_trials=1000, n_jobs=4)  # parallel
```

### pyfolio
For: Risk analysis post-backtest. Plots cumulative returns, rolling Sharpe, drawdown, rolling beta.
```python
import pyfolio
perf = pyfolio.utils.from_returns(strategy_returns)
# Plots risk metrics
```

### Alphalens
For: Factor analysis. If you have multiple signals, rank their contribution to returns.
```python
import alphalens
alphalens.tears.create_factor_tear_sheet(factor_data, returns)
```

---

## Architectural Takeaways for sleep-trading

1. **Start with mean reversion.** Simpler to code than trend-following; better in choppy markets.

2. **Walk-forward kills false positives.** Any strategy that "works" in-sample but fails out-of-sample is overfitted. Reject it early.

3. **Diversify signal sources.** Don't rely on one indicator (SMA). Combine RSI + MACD + Bollinger Bands. Redundancy improves robustness.

4. **Paper trade 2 weeks before live.** Many strategies that work in backtest fail in paper due to timing, order routing, or API quirks.

5. **Track signal confidence.** Don't trade every signal. Trade only when confidence > 0.7. This cuts trades and drawdowns.

6. **Avoid ML unless you have a PhD.** Overfitting is endemic. If you do use ML, strict walk-forward + out-of-sample validation only.

7. **Hedge with long-short.** A long-only trend follower loses 50% in a market crash. Long-short (long growth, short value) is more resilient.

## Sources

- [Algorithmic trading strategies explained - Moore Tech LLC](https://www.mooretechllc.com/algorithmic-trading/algorithmic-trading-strategies-explained/)
- [Mean reversion strategies - QuantInsti](https://blog.quantinsti.com/mean-reversion-strategies-introduction-building-blocks/)
- [Key algo trading strategies - Bookmap](https://bookmap.com/blog/key-algorithmic-trading-strategies-from-trend-following-to-mean-reversion-and-beyond/)
- [Optuna hyperparameter optimization - GitHub](https://github.com/optuna/optuna)
- [Statistical arbitrage - dYdX Learning](https://www.dydx.xyz/crypto-learning/statistical-arbitrage)
