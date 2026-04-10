# Research

Online research gathered to inform the design of the `sleep-trading` auto trading framework. The focus is on end-to-end pipeline architectures and tooling that an individual or small team (1–5 people, modest budget, no co-location) can realistically deploy across all asset classes (equities, crypto, FX, futures).

## Index

| Area | Description |
|---|---|
| [architecture/](./architecture/) | High-level system architectures and reference designs |
| [pipeline/](./pipeline/) | End-to-end pipeline stages: data → signal → strategy → execution → monitoring |
| [data-sources/](./data-sources/) | Market data feeds, vendors, and APIs |
| [execution-brokers/](./execution-brokers/) | Broker APIs, order routing protocols |
| [backtesting/](./backtesting/) | Backtest engines, walk-forward validation, simulation |
| [strategies/](./strategies/) | Strategy patterns and signal generation frameworks |
| [infrastructure-deployment/](./infrastructure-deployment/) | Cloud, containers, on-prem deployment patterns |
| [monitoring-risk/](./monitoring-risk/) | Observability, risk controls, kill switches |
| [open-source-frameworks/](./open-source-frameworks/) | Existing OSS trading frameworks |
| [case-studies/](./case-studies/) | Real individual / small-team setups |

Files in each subfolder will be populated by the research agent.

## Survey Files

Comprehensive research on the auto trading landscape (real sources only, verified April 2026):

1. **[architecture/survey.md](./architecture/survey.md)** — Reference architectures: event-driven vs request-response, microservices vs monolith, hybrid patterns for small teams. Includes ASCII diagrams of typical layouts.

2. **[pipeline/survey.md](./pipeline/survey.md)** — THE CENTERPIECE. End-to-end pipeline with 8 stages: ingestion, storage, feature engineering, signal generation, risk checks, order execution, post-trade reconciliation, monitoring. Each stage lists tools, data formats, failure modes, and mitigations.

3. **[data-sources/survey.md](./data-sources/survey.md)** — Market data vendors by asset class: Alpaca, Polygon, Tiingo, Databento (equities); CCXT, Kaiko (crypto); OANDA, TrueFX, HistData (FX); CME Group, IBKR (futures). Free tiers, pricing, API styles.

4. **[execution-brokers/survey.md](./execution-brokers/survey.md)** — Broker APIs: Alpaca, Interactive Brokers, Tradier (equities); Binance, Coinbase, Kraken (crypto); OANDA (FX). Paper trading availability, commission models, rate limits.

5. **[backtesting/survey.md](./backtesting/survey.md)** — Backtesting paradigms (vectorized vs event-driven), engines (VectorBT, Backtrader, Zipline, Nautilus), walk-forward analysis, look-ahead bias prevention, slippage modeling.

6. **[strategies/survey.md](./strategies/survey.md)** — Strategy archetypes (trend, mean reversion, market making, stat arb, ML-based, options vol). Research workflow: notebook → vectorized backtest → Optuna optimization → event-driven backtest → paper trading → live.

7. **[infrastructure-deployment/survey.md](./infrastructure-deployment/survey.md)** — Deployment patterns for small teams: single VPS, Docker Compose on VPS, hybrid (research cloud + live execution VPS), serverless (scheduled jobs). State management, storage (TimescaleDB, DuckDB, Parquet).

8. **[monitoring-risk/survey.md](./monitoring-risk/survey.md)** — Risk controls (position limits, daily loss kill-switch, max drawdown halt). Monitoring stacks (Prometheus + Grafana + Sentry). Alerting (Telegram, Slack, PagerDuty). Reconciliation jobs.

9. **[open-source-frameworks/survey.md](./open-source-frameworks/survey.md)** — Comparison table of 10+ OSS frameworks (QuantConnect Lean, Nautilus Trader, Backtrader, Zipline-Reloaded, Freqtrade, Hummingbot, VectorBT, Backtesting.py, StockSharp). Languages, licenses, asset classes, live trading, activity, learning curves.

10. **[case-studies/survey.md](./case-studies/survey.md)** — Real deployments by solo traders and small teams: AWS workshop (equities), NautilusTrader user (ES + crypto), Docker Compose system (crypto ML), Reddit writeup (equity mean reversion), startup trio (equities + options). Key lessons: paper trading catches surprises, slippage kills edge, operational risk > model risk.
