# Pipeline Survey

## Summary

An end-to-end algorithmic trading pipeline spans eight stages from raw market data through post-trade reconciliation. Each stage has distinct failure modes, latency budgets, and tool choices. Small teams must prioritize the critical path (data → signal → execution) while automating housekeeping (reconciliation, alerting). Pipeline design for sleep-trading emphasizes separation of concerns (no single point of failure) and clear data contracts between stages to enable team parallelization and strategy swaps.

## Full Pipeline with Stages

```
Market Feeds          Ingestion           Storage          Feature Calc
(Polygon, Binance)  ─────────────────→ (Postgres)  ────→  (Numpy/Pandas)
    │                  │ Error queue    TimescaleDB      Signal generation
    ├─ Real-time      └─ Backfill       │                 │
    └─ Historical        queue           └─────────────────┤
                                                           │
                                                Signal → Strategy → Risk → Execution
                                                Logic   (Python) Checks  (Broker API)
                                                │       Decision │  Pos  │  Order
                                                │       Layer    │ Limits│  Gen
                                                └──────────────────┴──────┘
                                                         │
                                                   ┌─────▼──────────┐
                                                   │ Monitoring &   │
                                                   │ Alerting       │
                                                   │ (Prometheus,   │
                                                   │  Loki)         │
                                                   └────────────────┘
                                                         │
                                                    Post-Trade
                                                    ├─ Fills reconciliation
                                                    ├─ P&L calc
                                                    └─ Report generation
```

## Stage-by-Stage Breakdown

### 1. Market Data Ingestion

**What flows through:** Raw ticks, OHLCV bars, L2 orderbook snapshots, trades.

**Common tools:**
- Real-time: WebSocket connections (asyncio in Python, tokio in Rust)
- Batch/backfill: REST APIs with pagination (Polygon, Alpaca, Databento)
- Message broker: Kafka (distributed) or Redis Streams (single-host)

**Data formats:** Protocol Buffers or JSON for messages; parquet for batch storage.

**Failure modes:** Exchange downtime, data gaps (ask for 5m data, get 4m), duplicate ticks, out-of-order packets.

**Mitigations:** 
- Multiple feed redundancy (Polygon + Tiingo fallback)
- Tick deduplication by exchange timestamp + sequence number
- Dead-letter queue for unparseable messages

---

### 2. Storage / Time-Series Database

**What flows through:** Deduplicated, ordered ticks; calculated OHLCV.

**Common tools:**
- Postgres + TimescaleDB extension (transactional, ACID; good for <1TB)
- ClickHouse (columnar OLAP; excellent for scan-heavy analytics)
- DuckDB (local, single-file OLAP; no infra overhead)
- Parquet on S3 (immutable data lake; cost-effective archive)

**Data formats:** Columnar (Parquet), row-based (Postgres). Use foreign data wrappers to bridge them.

**Failure modes:** Disk full, replication lag (if distributed), slow queries blocking ingest.

**Mitigations:**
- Autovacuum & partitioning by date in Postgres
- ClickHouse MergeTree with TTL policies
- Separate read replicas for backtest queries

---

### 3. Feature & Signal Generation

**What flows through:** Raw OHLCV → computed indicators (RSI, Bollinger Bands, ML embeddings).

**Common tools:**
- Pandas/NumPy (vectorized; good for backtests)
- TA-Lib, pandas-ta (technical indicators)
- Prophet, ARIMA (time-series forecasting)
- Custom ML (scikit-learn, XGBoost) for alpha signals

**Data formats:** DataFrames (in-memory) or Parquet (batch precompute).

**Failure modes:** Data look-ahead bias, NaN handling (missing OHLCV), indicator lag interpretation.

**Mitigations:**
- Strict time boundaries (e.g., signal uses only data up to T-5min, not T)
- Pre-compute indicators overnight as cached Parquet
- Unit tests with known OHLCV sequences

---

### 4. Strategy Logic & Decision Layer

**What flows through:** Feature vectors → buy/sell/hold signals.

**Common tools:**
- Pure Python logic (simple rules, no ML)
- Pickle/joblib (stateful models loaded from disk)
- TensorFlow Lite (lightweight inference for edge)

**Data formats:** Signal events (ticker, timestamp, direction, confidence).

**Failure modes:** Strategy crashes due to NaN, edge cases in data (ticker delisted, split), model staleness.

**Mitigations:**
- Graceful error handling with fallback to neutral
- Nightly model retraining + A/B test on paper first
- Strategy versioning (v1.0, v1.1) with instant rollback

---

### 5. Risk & Position Management

**What flows through:** Proposed orders from strategy; position inventory; P&L snapshots.

**Common tools:**
- Custom state machine (Python dataclasses or Pydantic models)
- Postgres for durable state
- Redis for fast cache (position delta hedge, VaR)

**Data formats:** Order events (status, fill price, qty, time); position records (ticker, qty, avg_cost, current_price).

**Failure modes:** Double orders (network retries), position overshoots, stale price data for Greeks (options).

**Mitigations:**
- Idempotent order submission (unique order IDs)
- Position limits enforced before order generation
- Max drawdown kill switch checked on every fill
- Notional exposure cap per ticker/sector

---

### 6. Order Generation & Execution

**What flows through:** Risk-approved orders → broker API → filled orders.

**Common tools:**
- Alpaca API (REST/WS; best for small teams on US equities)
- Interactive Brokers API (wider asset class; FIX + REST)
- Binance/Kraken WebSocket (crypto)
- CCXT unified wrapper (abstracts exchange differences)

**Data formats:** Order structure (ticker, side, qty, type, time_in_force); fill confirmations (execution_id, fill_price, fill_qty, ts).

**Failure modes:** Order rejection (insufficient buying power), partial fills, exchange outage, slippage > expected.

**Mitigations:**
- Pre-check buying power before submission
- Heartbeat to detect broker disconnection (ping broker every 30s)
- Timeout + manual cleanup job for stuck orders
- Slippage model in backtest matches historical execution

---

### 7. Post-Trade Reconciliation

**What flows through:** Broker fills vs. internal order tracker.

**Common tools:**
- Daily Postgres job querying broker for all fills since yesterday
- Comparison against order_events table
- Slack alert if discrepancies found

**Data formats:** Reconciliation report (expected vs. actual qty, price, commissions).

**Failure modes:** Broker API downtime (can't fetch fills), time-zone mismatches, commission misclassification.

**Mitigations:**
- Idempotent reconciliation (safe to run twice)
- Webhook from broker if supported (Alpaca provides this)
- Manual review process for >$X discrepancies

---

### 8. Monitoring, Alerting, and Reporting

**What flows through:** Metrics (P&L, fill rate, latency) → dashboards & alerts.

**Common tools:**
- Prometheus (metrics scrape + storage)
- Grafana (dashboards)
- Loki (log aggregation)
- AlertManager (rule evaluation)
- Telegram/Slack webhooks (notifications)

**Data formats:** Prometheus time-series (counter, gauge, histogram); JSON logs.

**Failure modes:** Dashboard lag, alert fatigue (too many False alarms), silent failures (metrics not emitted).

**Mitigations:**
- Push critical metrics every tick (P&L, position delta)
- Silence non-critical alerts outside market hours
- Healthcheck endpoint that returns system state
- Weekly report email (trades executed, total return, worst day)

---

## Data Flow & Format Standards

| Stage Boundary | Format | Latency SLA | Notes |
|---|---|---|---|
| Ingestion → Storage | Parquet batch + live queue | <100ms | Dedup on exchange seq# |
| Storage → Features | Pandas DataFrame | <500ms | Pre-compute if possible |
| Features → Strategy | Signal events (JSON) | <1s | Single point of rate limit |
| Strategy → Risk | Order intent (dict) | <100ms | Synchronous (not queued) |
| Risk → Execution | Approved order (dict) | <50ms | Hot path; minimal object copy |
| Execution → Monitoring | Fill event | <100ms | Log immediately on confirmation |
| Everything → Postgres | Async batch write | <5s | Tolerance for reorder on recovery |

## Architectural Takeaways for sleep-trading

- **Decouple stages with message queues, not RPC.** Use Redis Streams or Kafka to separate ingest from calculation; a hung strategy doesn't block data collection.

- **Pre-compute features offline.** Run a nightly job that calculates all indicators for tomorrow; avoids runtime CPU spikes and indicator look-ahead bugs.

- **Make risk checks synchronous.** Queries to Postgres for position state must return in <100ms; use Redis cache if needed.

- **Log everything with structured format.** Every signal, order, and fill should produce a JSON entry with timestamp. Parse in Loki for alerting.

- **Test failure modes:** simulate feed downtime, exchange rejection, and slow Postgres queries. Document recovery steps.

- **Avoid backfill re-trading.** When fetching historical ticks to build the initial database, disable live strategy execution. Prevents accidental duplicate trades.

## Sources

- [Google Cloud: Building Real-Time Data Pipelines for Capital Markets](https://cloud.google.com/blog/topics/financial-services/building-real-time-data-pipelines-for-capital-markets-firms)
- [Tradewink: AI Day Trading Pipeline](https://www.tradewink.com/learn/ai-day-trading-pipeline)
- [Realtime Data Pipeline GitHub — Jimmymugendi](https://github.com/Jimmymugendi/Realtime-Data-Pipeline-for-Stock-Market-Analysis)
- [Data Pipeline Design in Algorithmic Trading — Medium](https://medium.com/@edwinsalguero/data-pipeline-design-in-an-algorithmic-trading-system-ac0d8109c4b9)
- [Kafka + PostgreSQL for Finance — Integrate.io](https://www.integrate.io/blog/data-pipelines-finance-industry/)
