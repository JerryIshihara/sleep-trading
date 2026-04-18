# End-to-End Trading Pipeline: Stages, Tools, and Data Flows

## Summary

A production trading pipeline is a sequence of stages, each transforming raw market data into executed trades and monitored positions. Unlike simple workflows, the pipeline must handle real-time ingestion, feature engineering, strategy logic, risk controls, and post-trade reconciliation. This survey describes each stage, the tools and formats in use, and the failure modes a small team must defend against. The pipeline is inherently event-driven: a price tick triggers feature calculation, which triggers signal generation, which (if risk checks pass) triggers order submission, fills ripple back through the system, and the cycle repeats thousands of times per day.

## Pipeline Architecture Diagram

```
MARKET DATA (real-time or batch)
    ↓
[1] INGESTION: WebSocket/REST poll → normalize → enqueue
    ↓ (tick events)
[2] STORAGE: TimescaleDB / ClickHouse (append-only)
    ↓ (OHLC bars, tick history)
[3] FEATURE & SIGNAL: rolling windows → compute stats → generate signals
    ↓ (buy/sell/hold signals, confidence scores)
[4] STRATEGY LOGIC: combine signals → position sizing → pre-trade risk checks
    ↓ (order proposals: symbol, qty, side, type)
[5] RISK & POSITION MGT: enforce limits → kill-switch logic
    ↓ (final orders: approved or rejected)
[6] ORDER GENERATION & EXECUTION: submit to broker → track status
    ↓ (fills, partial fills, rejections)
[7] POST-TRADE RECONCILIATION: broker book ↔ our ledger
    ↓ (confirm fills, update P&L)
[8] MONITORING, ALERTING & REPORTING: metrics → dashboards → alerts
    ↓ (human oversight, machine alerting)
LIVE POSITION SNAPSHOT & P&L REPORT
```

## Stage 1: Market Data Ingestion

**Goal:** Acquire real-time or near-real-time market data from exchanges without missing events or duplicating data.

**Tools:**
- **WebSocket:** Alpaca, Binance, Kraken, Interactive Brokers (via TWS), Coinbase
- **REST polling:** backup when WebSocket unavailable; OANDA (FX), CME (futures)
- **Unified libraries:** CCXT (crypto), ib_insync (IBKR equities/futures/options), yfinance (EOD historical)

**Data formats:**
- **Tick:** `{symbol, timestamp, bid, ask, last_price, volume, exchange, source}`
- **Bar (OHLC):** `{symbol, timestamp, open, high, low, close, volume}`
- **Level 2 order book:** `{symbol, bids: [(price, qty), ...], asks: [(price, qty), ...]}`

**Failure modes & mitigations:**
- *Connection drop:* Keep a heartbeat timer; reconnect with exponential backoff (1s → 30s).
- *Duplicate ticks:* Deduplicate by (symbol, exchange, timestamp, price); discard exact repeats.
- *Out-of-order events:* Buffer 100ms and sort by timestamp before processing.
- *Slow feeder:* Use a separate thread/async task; never block the main loop.

**For small teams:** Prioritize two exchanges per asset class (primary + fallback). Alpaca for US equities, Binance for spot crypto, IBKR for futures. One ingestion script per asset class; each can fail independently.

---

## Stage 2: Storage (Time-Series Database)

**Goal:** Persist market data durably so backtests can replay history and live trading can look back for feature engineering.

**Tools:**
- **TimescaleDB (Postgres extension):** Best all-rounder for small teams. Compression, retention policies, hypertables. Run on a single VPS.
- **ClickHouse:** High ingest rates (millions of rows/sec), columnar compression, excellent for historical analytics. Overkill if you have <1M bars/day.
- **DuckDB:** In-process analytical database; no server. Good for research. Can query Parquet on S3 directly.
- **InfluxDB:** Purpose-built for metrics/time-series. Lightweight. Not ideal for transactional consistency (orders).

**Data layout (TimescaleDB example):**
```sql
CREATE TABLE market_data (
  time TIMESTAMPTZ,
  symbol TEXT,
  exchange TEXT,
  price NUMERIC,
  volume NUMERIC,
  bid NUMERIC,
  ask NUMERIC
);
SELECT create_hypertable('market_data', 'time');
-- Automatic chunking by day, compression, TTL policies
```

**Failure modes:**
- *Disk full:* Set retention policies (e.g., keep ticks for 3 days, bars for 2 years).
- *Insert lag:* Use batch inserts (100s of records per query), not one-by-one.
- *Query timeout on backtest:* Index by (symbol, time). Pre-aggregate OHLC bars nightly.

---

## Stage 3: Feature & Signal Generation

**Goal:** Transform raw market data into interpretable features (volatility, trend, momentum) and trading signals (buy, sell, hold).

**Tools:**
- **Ta-lib, pandas-ta:** Technical indicator libraries.
- **Polars, pandas:** Vectorized feature computation. Pandas + NumPy for rolling windows.
- **Custom Python functions:** For proprietary signals or ML-based inference.

**Data flows:**
- Input: `market_data` table (tick or OHLC bars).
- Compute: Rolling means, volatility, RSI, MACD, etc.
- Output: `signals` table: `{symbol, timestamp, signal, confidence, reason}`.

**Example (mean-reversion signal):**
```python
def compute_signal(bars: pd.DataFrame) -> float:
    close = bars['close'].values
    sma_20 = close[-20:].mean()
    std_20 = close[-20:].std()
    zscore = (close[-1] - sma_20) / std_20
    if zscore < -1.5: return 1.0  # buy
    elif zscore > 1.5: return -1.0  # sell
    else: return 0.0  # hold
```

**Failure modes:**
- *Look-ahead bias:* Never use future data (close price at t+1) to generate signal at t. Strict data cutoff.
- *Stale features:* If market data stalls, features become stale. Use timestamps, not row counts.
- *NaN propagation:* Handle missing data explicitly (drop, forward-fill, or skip).

---

## Stage 4: Strategy Logic & Decision Layer

**Goal:** Take signals and context (portfolio, risk limits) and decide whether to trade.

**Tools:**
- **In-process strategy engine:** No external library needed for simple rules.
- **Backtrader, Zipline:** For simulation.
- **Custom Python class:** Holds state (open positions, portfolio value) and makes decisions.

**Data flows:**
- Input: `signals`, portfolio state (cash, positions), risk params (max_pos, max_loss).
- Logic: If signal > 0.8 and market_cap > $100M and no position and cash_available > min_order_size, generate order.
- Output: `order_proposals` table: `{symbol, side, qty, order_type, time_in_force}`.

**Sizing example (Kelly fraction):**
```python
# Rough Kelly-inspired sizing: qty = portfolio * kelly_fraction * signal_strength
portfolio_value = cash + sum(pos_value for each open position)
kelly_frac = 0.1  # conservative
signal_strength = abs(signal)
qty = int(portfolio_value * kelly_frac * signal_strength / price)
```

**Failure modes:**
- *Stale portfolio state:* Query positions from database at strategy start.
- *Rounding errors:* qty must be an integer; sum of qty * price must not exceed cash.
- *Fat finger:* Always size orders relative to portfolio, never absolute.

---

## Stage 5: Risk & Position Management

**Goal:** Enforce position limits, max drawdown, and kill-switch logic before any order hits the broker.

**Tools:**
- **Custom risk engine:** A few hundred lines of Python.
- **Prometheus + Grafana + custom alerts:** Monitoring and alerting.

**Checks (apply in order):**
1. **Position cap:** No symbol > X% of portfolio.
2. **Sector concentration:** No finance sector > Y% of portfolio.
3. **Max open orders:** Don't let order count exceed N.
4. **Daily loss limit:** If realized losses today > Z%, halt all orders (kill-switch).
5. **Max drawdown:** If portfolio value < 90% of peak, halt.
6. **Liquidity:** Reject if order size > daily volume / 10.

**Example (Python):**
```python
def risk_check(order: Order, positions: Dict, limits: Dict) -> bool:
    if order.qty * order.price > limits['max_position_value']:
        return False  # Position cap violated
    if sum_losses_today > limits['daily_loss_limit']:
        return False  # Kill-switch: halt
    if portfolio_value < peak_portfolio * 0.9:
        return False  # Max drawdown halt
    return True  # Order approved
```

**Failure modes:**
- *Slippage in risk calc:* If portfolio worth $100k and order is for $50k, the post-order portfolio is $50k. Recalculate limits after each order.
- *Stale positions:* Query latest positions before each order.
- *Kill-switch lag:* Check limits at microsecond granularity; reject orders atomically.

---

## Stage 6: Order Generation & Execution

**Goal:** Submit approved orders to one or more brokers and track status (pending, filled, rejected, cancelled).

**Tools:**
- **Broker SDKs:** Alpaca (REST/WebSocket), ib_insync (Interactive Brokers), ccxt (crypto), OANDA (FX).
- **Order management system (OMS):** Custom state machine to track fills and partial fills.

**Data flows:**
- Input: Approved `order_proposals`.
- Action: Submit to broker API.
- Output: `orders` table: `{order_id, symbol, side, qty, filled_qty, status, timestamp}`.

**Example (Alpaca):**
```python
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest

trade_client = TradingClient(api_key, secret_key, paper=True)
order_req = MarketOrderRequest(symbol=symbol, qty=qty, side=side)
order = trade_client.submit_order(order_req)
# order.id, order.status, order.filled_qty, order.filled_avg_price
```

**Failure modes:**
- *Broker rejection (e.g., pattern day trader rule):** Catch and log. Pause strategy. Alert operator.
- *Order stuck in 'pending':** Set a timeout (e.g., cancel if not filled in 30 seconds).
- *Partial fills:** Track qty_filled vs qty_ordered. Generate a new order for remainder if strategy still valid.
- *Network split:* Order submitted but response lost. Query broker's open orders list every 10 seconds; reconcile with local ledger.

---

## Stage 7: Post-Trade Reconciliation

**Goal:** Ensure our ledger matches the broker's after every fill.

**Tools:**
- **Cron job:** Run hourly.
- **Broker API:** Query open orders and positions.
- **Custom reconciliation script (100 lines).**

**Process:**
1. Get our open orders from database.
2. Get broker's open orders via API.
3. For any mismatch, log an alert and escalate (e.g., disable strategy, page operator).
4. Get our positions from database.
5. Get broker's positions via API.
6. Reconcile P&L.

**Example mismatch (could indicate a bug or broker issue):**
- We think we have 100 shares of AAPL; broker says 95. Likely partial fill arrived but not processed. Replay fill events, update ledger.

**Failure modes:**
- *Timestamp skew:* If reconciliation runs between a fill happening and our ledger being updated, false alarm. Build a 2-minute grace period.
- *Multi-currency conversion:* If trading FX or international, apply realistic FX rates.

---

## Stage 8: Monitoring, Alerting & Reporting

**Goal:** Give humans and machines visibility into live trading: what's happening, what's broken, what's profitable.

**Tools:**
- **Prometheus:** Scrape metrics every 10 seconds.
- **Grafana:** Live dashboards (P&L, position summary, order fill rate).
- **Sentry:** Catch exceptions in strategy code.
- **Telegram bot or Slack webhook:** Alert operator to critical events (kill-switch, order rejection, reconciliation failure).
- **Structured logging (JSON):** Feed to Loki or ELK for searchability.

**Key metrics:**
- `portfolio_value`, `realized_pnl`, `unrealized_pnl` (updated after each fill).
- `open_positions_count`, `open_orders_count`.
- `strategy_latency` (signal generated to order submitted).
- `broker_latency` (order submitted to fill received).
- `fills_per_minute`, `rejection_rate`.

**Example Grafana dashboard:**
```
┌─ Portfolio Value  ─ P&L (Today)  ─ Drawdown ─┐
│ $97,453           +2.3%            -3.2%     │
├─────────────────────────────────────────────┤
│ Open Positions: 5                             │
│   AAPL: 100 @ $152.30 (unrealized: +$230)   │
│   GOOG: 50 @ $140.15 (unrealized: -$120)    │
├─────────────────────────────────────────────┤
│ P&L by Hour [chart]                         │
│ Order Fills [chart]                         │
│ Latency Histogram [chart]                   │
└─────────────────────────────────────────────┘
```

**Alerts (Telegram/Slack):**
- Order rejected by broker (symbol, qty, reason).
- Kill-switch activated (daily loss threshold hit).
- Reconciliation failure (our ledger ≠ broker).
- Strategy exception (traceback, then disable strategy).
- Broker connection lost (reconnecting...).

---

## Architectural Takeaways for sleep-trading

1. **Ingest and store separately.** Don't backtest directly against live WebSocket. Persist all market data to TimescaleDB immediately; backtest reads from DB.

2. **Signals are cheap; orders are expensive.** Generate signals for 1000 symbols; execute on only 50. Signals cost CPU; orders cost fees and slippage.

3. **Deduplicate and order events.** Network delivers ticks out of order. Buffer 100ms, sort, then process.

4. **Risk checks are binary and fast.** No floating-point math. All comparisons should be atomic (no risk of race condition). Reject aggressively.

5. **Reconciliation is your insurance policy.** Run hourly. It catches bugs, broker glitches, and fat fingers before they blow up.

6. **Monitor latency, not just P&L.** If order latency rises from 100ms to 5s, your edge erodes even if it's not live yet. Measure everything.

7. **Separate live from backtest paths.** Backtest reads historical data from database. Live reads from WebSocket. Different data sources, different code paths, both validation.

## Sources

- [Data Pipeline Design in Algorithmic Trading - Medium](https://medium.com/@edwinsalguero/data-pipeline-design-in-an-algorithmic-trading-system-ac0d8109c4b9)
- [AI Day Trading Bots Pipeline - Tradewink](https://www.tradewink.com/learn/ai-day-trading-pipeline)
- [Real-time data pipelines for capital markets - Google Cloud](https://cloud.google.com/blog/topics/financial-services/building-real-time-data-pipelines-for-capital-markets-firms)
- [Backtesting and walk-forward analysis - Interactive Brokers](https://www.interactivebrokers.com/campus/ibkr-quant-news/the-future-of-backtesting-a-deep-dive-into-walk-forward-analysis/)
