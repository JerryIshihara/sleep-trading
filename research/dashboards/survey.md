# Trading Dashboard Examples

## Summary

A good dashboard for a small-team auto trading system must balance real-time awareness with actionable clarity: monitor live P&L, open positions, and order fill rates at a glance, while surfacing strategy-level metrics (Sharpe ratio, drawdown, win rate) and system health signals (latency, broker connection, errors) without information overload. Successful dashboards use responsive web frameworks (Streamlit, Plotly Dash, React) combined with time-series monitoring tools (Grafana+Prometheus) to provide both high-level portfolio health and drill-down capability into individual trade flows. The best examples separate concerns into linked panels: market charts, portfolio snapshots, performance analytics, and ops alerts.

## Category 1: Market Data Dashboards

- **TradingView Lightweight Charts** — Industry-standard candlestick charting library used in custom trading apps. [link](https://www.tradingview.com/scripts/candlestick/)
  - Stack: JavaScript/TypeScript library, embeddable in React, Vue, Streamlit
  - Displays: Candlestick OHLC bars, real-time candles, custom indicators, price levels
  - Layout: Full-screen chart with overlay indicators and session-based reference levels
  - Takeaway: Use TradingView's Lightweight Charts library for candlestick rendering instead of building from scratch; integrates well with Dash/Streamlit via Plotly wrappers or custom React components.

- **Plotly Dash Technical Charting** — Production demo of interactive technical charting in pure Python. [link](https://github.com/plotly/dash-technical-charting)
  - Stack: Plotly Dash (Python web framework), responsive Bootstrap layout
  - Displays: Multi-timeframe candlesticks, moving averages, volume bars, interactive legend
  - Layout: Tabbed interface with controls for symbol selection and timeframe switching
  - Takeaway: Plotly Dash can handle interactive financial charting without JavaScript; suitable for embedding in sleep-trading's market data module.

- **Dash TradingView Component Wrapper** — Python wrapper integrating TradingView's Lightweight Charts into Plotly Dash. [link](https://github.com/tysonwu/dash-tradingview)
  - Stack: Python Dash component, wraps JavaScript Lightweight Charts
  - Displays: Candlesticks, indicators, real-time updates, custom drawing tools
  - Layout: Embedded trading chart with overlaid studies and annotations
  - Takeaway: Bridges Plotly Dash and TradingView charting—ideal for a Python-native backend with best-in-class charting UI.

## Category 2: Portfolio & Positions Dashboards

- **Freqtrade FreqUI** — Built-in web UI for the Freqtrade open-source crypto trading bot. [link](https://github.com/freqtrade/freqtrade)
  - Stack: Freqtrade REST API with responsive web frontend (Vue.js)
  - Displays: Trade table (entry/exit, P&L per trade), open positions, balance summary, order status
  - Layout: Tabbed navigation—Trades view, General info, Configuration, Backtesting results
  - Takeaway: Reference how Freqtrade separates live trades from configuration UI; the trade table with entry price, current price, and P&L per row is essential for position monitoring.

- **Hummingbot Dashboard** — Streamlit-based dashboard for multi-bot orchestration and performance monitoring. [link](https://github.com/hummingbot/dashboard)
  - Stack: Streamlit (Python data app framework), multi-instance deployment
  - Displays: Portfolio history (equity curve), active controllers per bot, current bot status, asset allocation
  - Layout: Sidebar bot selector, main panel showing selected bot's performance graph and controller config
  - Takeaway: Hummingbot's per-instance portfolio chart and unified multi-bot orchestration UI shows how to scale dashboard design across multiple strategies.

- **Base Trading Dashboard** — Plotly Dash app for backtesting and live portfolio visualization. [link](https://github.com/dang-trung/base-trading)
  - Stack: Plotly Dash with Dash Bootstrap Components, Yahoo Finance data source
  - Displays: Prices and entry/exit markers, portfolio value over time, returns + volatility metrics, Sharpe ratio comparison
  - Layout: Sidebar controls (ticker, entry/exit patterns), main Plotly chart with candlesticks and trade annotations
  - Takeaway: Demonstrates how to overlay trade markers (entry, exit) on price chart and show key risk metrics (Sharpe, returns) alongside; replicable pattern for sleep-trading.

- **Stock Portfolio Dashboard** — Grafana community dashboard for tracking portfolio holdings and P&L. [link](https://grafana.com/grafana/dashboards/15956-stock-portfolio/)
  - Stack: Grafana with Prometheus time-series backend
  - Displays: Total portfolio value, per-asset holdings (table), realized and unrealized gains, asset allocation pie chart
  - Layout: Top-level KPI cards, multi-row table of positions, time-series value chart
  - Takeaway: Grafana's table-based position display and easy KPI card layout are effective for ops teams monitoring multiple trading instances.

## Category 3: Strategy Performance Dashboards

- **Freqtrade-Grafana Solution** — Community project combining Freqtrade, Prometheus, and Grafana for multi-strategy comparison. [link](https://github.com/thraizz/freqtrade-dashboard)
  - Stack: Grafana + Prometheus scrapers + Freqtrade REST API
  - Displays: Per-strategy Sharpe ratio, drawdown (%), win rate, trade count, profit curves side-by-side
  - Layout: Strategy comparison view with metrics table, equity curves overlaid for visual comparison
  - Takeaway: Shows how to surface per-strategy performance metrics at a glance; Prometheus + Grafana is production-standard for time-series metrics in trading ops.

- **QuantConnect Backtest Report** — Cloud IDE's backtest results viewer with equity curve and performance breakdown. [link](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results)
  - Stack: Cloud web UI (proprietary), PDF report generation
  - Displays: Equity curve with drawdown periods (colored bands), trade log (entry/exit/P&L), Sharpe ratio, max drawdown, win rate, trade statistics (avg win/loss, holding periods)
  - Layout: Left sidebar metric cards (Sharpe, Return %, Max DD), main chart area (equity + drawdown overlay), tabbed drill-down (trades, logs, performance breakdown)
  - Takeaway: QuantConnect's metric cards + equity chart + drawdown bands visual pattern is industry-standard; copyable design for sleep-trading's backtest/live performance view.

- **AI-Predictor Dashboard** — React/Vite dashboard for multi-strategy MetaTrader 5 trading system with real-time monitoring. [link](https://github.com/Son930/AI-Predictor)
  - Stack: React/Vite frontend, FastAPI backend, WebSocket real-time data
  - Displays: Strategy comparison table (return, Sharpe, recent trades), equity curve, per-strategy P&L, model prediction confidence
  - Layout: Dashboard tabs—strategy overview, individual strategy drill-down with live signals, backtest comparison charts
  - Takeaway: Shows modern JavaScript framework (React) approach to multi-strategy monitoring; useful if sleep-trading moves beyond Python-only frontend.

- **LLM-Trader Dashboard** — Streamlit app for AI trading bot with trade history, decision logs, and strategy metrics. [link](https://github.com/HKUDS/AI-Trader)
  - Stack: Streamlit (Python)
  - Displays: Equity curve vs. BTC buy-and-hold benchmark, recent trades (table: symbol, entry, exit, P&L), AI decision reasoning logs, per-trade confidence scores
  - Layout: KPI metric row at top (total return, Sharpe, max DD), main equity curve chart, trade log table below
  - Takeaway: Benchmarking equity curve against buy-and-hold is a strong reference; showing AI decision logs next to P&L builds trust in automated systems.

## Category 4: System Health / Ops Dashboards

- **Grafana+Prometheus for Trading Bots** — General pattern for monitoring trading system latency, error rates, and resource usage. [link](https://grafana.com/docs/grafana/latest/fundamentals/getting-started/first-dashboards/get-started-grafana-prometheus/)
  - Stack: Prometheus (metrics collection), Grafana (visualization)
  - Displays: Request latency (P50, P95, P99), error rate (%), order fill rate, broker API uptime, CPU/memory per bot instance
  - Layout: KPI cards for critical metrics (uptime %), time-series panels for latency/error rate, single-stat gauges for fill rate
  - Takeaway: Standard ops pattern; critical for sleep-trading to instrument order execution and broker connection health with Prometheus counters and histograms.

- **Cryptohopper Dashboard** — Crypto trading bot's real-time control panel showing current state. [link](https://docs.cryptohopper.com/docs/trading-bot/dashboard/)
  - Stack: Web UI (proprietary)
  - Displays: Open orders (table), active positions, reserved funds, current profit, bot status (enabled/disabled), panic button, activity log, exchange sync status
  - Layout: Status indicators and controls at top, open orders / positions table, activity feed sidebar
  - Takeaway: "Panic button" (stop all trading) and activity feed are essential for ops safety; reserved funds visibility prevents over-allocation.

- **Hummingbot Monitor (Community Grafana)** — Third-party Grafana setup for monitoring Hummingbot instances. [link](https://github.com/afansky/hummingbot-monitor)
  - Stack: Grafana + Docker Compose, exposes Hummingbot API metrics
  - Displays: Bot uptime per instance, order flow (trades per minute), balance changes, strategy status
  - Layout: Instance selector dropdown, multi-panel overview with time-series charts
  - Takeaway: Docker-composable ops dashboard; reference for instrumenting multi-instance bots (useful for sleep-trading's planned support of multiple strategies).

## ASCII Sketch of a Recommended sleep-trading Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│ sleep-trading LIVE MONITOR                        [🔄 refresh] [⚙️ config] │
├──────────────────┬──────────────────────────────────────────────────────┤
│ PORTFOLIO HEALTH │                 MARKET DATA & POSITIONS              │
├──────────────────┤                                                      │
│ Total Equity     │  ┌───────────────────┐  ┌───────────────────────┐  │
│ $47,230 ↑ 3.2%   │  │  ETH/USD 4H       │  │ OPEN POSITIONS        │  │
│                  │  │  [Candlesticks]   │  │ ┌─────────────────┬──┐  │  │
│ Sharpe: 1.84     │  │  MA(20), MA(50)   │  │ │ Symbol │ Entry │QT│  │  │
│ Max DD: -8.1%    │  │                   │  │ ├─────────────────┼──┤  │  │
│ Win Rate: 61%    │  │                   │  │ │ ETH    │ 1845 │+5│  │  │
│                  │  │ Last 24h Vol      │  │ │ BTC    │22100 │-2│  │  │
│ ────────────────  │  │ 3.2M              │  │ │ AAPL   │178.2 │+20  │  │
│ DAY P&L          │  │                   │  │ └─────────────────┴──┘  │  │
│ +$542 ↑          │  │                   │  │                        │  │
│ (+1.16%)         │  │                   │  │ Open Orders: 2         │  │
│                  │  │                   │  │ Reserved: $4,200       │  │
│                  │  └───────────────────┘  └───────────────────────┘  │
├──────────────────┼────────────────────────────────────────────────────┤
│ STRATEGY PERF    │          SYSTEM HEALTH / OPS                        │
├──────────────────┤                                                     │
│ Strategy: RSI_MA │ ┌─────────────────┬─────────────────┬────────────┐ │
│ Status: LIVE     │ │ Broker: LIVE ✓  │ Orders Filled   │ Latency    │ │
│ Trades: 24       │ │ API: 99.8% ↑    │ 94.2% (47/50)   │ 187ms avg  │ │
│ Avg Win: $125    │ │ Sync: OK ✓      │                 │ Last 1h: ✓ │ │
│ Avg Loss: $82    │ └─────────────────┴─────────────────┴────────────┘ │
│ Profit Factor: 1.52 │                                                  │
│                  │ Activity Feed:                                       │
│ [STOP] [LOG]     │ 14:23 Order filled: ETH/USD +5 @ 1845              │
│                  │ 14:21 RSI signal: Bullish (24.5 → 67.3)            │
│                  │ 14:19 Balance update: $47,230                      │
│                  │ 14:18 Monitoring: No open errors                   │
│                  │                                                     │
└──────────────────┴────────────────────────────────────────────────────┘
```

## Architectural Takeaways for sleep-trading

- **Separation of Concerns**: Split the UI into independent, linked panels—market data (Plotly or TradingView), portfolio state (tables), strategy metrics (time-series), and ops alerts (Grafana cards). Each can be swapped or updated independently.

- **Backend Integration**: Use REST API for read-heavy market/portfolio data (low-latency JSON), and Prometheus metrics + Grafana for write-heavy operational telemetry (errors, fill rates, latency). This pattern scales across multiple bots.

- **Framework Choice**: For a Python-native system, Streamlit is fast for prototyping and Plotly Dash is more customizable for production dashboards. If ops teams need Grafana, instrument the bot with Prometheus `prometheus_client` library to expose metrics at `http://localhost:8000/metrics`.

- **Critical Metrics**: Always surface (1) total equity, (2) day P&L, (3) open positions (live table), (4) order fill rate, (5) broker connection status, and (6) last 3–5 activity log entries. Everything else is drill-down.

- **Safety Controls**: Include a "Panic Stop" button to halt all orders immediately; display reserved capital so users see real available margin. Log every action (order submit, fill, error) to the feed.

- **Multi-Strategy View**: If supporting multiple strategies/bots, use a selector or tabs to isolate performance metrics per strategy, but show unified portfolio equity to catch correlated drawdowns.

- **Real-Time Updates**: Use WebSocket or server-sent events for P&L and order fills; poll REST API for low-frequency data (portfolio rebalance, broker account sync). Freqtrade and Hummingbot use this pattern.

- **Visualization Patterns**: Overlay trade entry/exit markers on candlestick charts (Base Trading Dashboard pattern); use equity curve + colored drawdown bands (QuantConnect pattern); table rows for position drill-down (Freqtrade pattern). These are proven by users.

## Sources

- [Freqtrade](https://github.com/freqtrade/freqtrade)
- [Hummingbot Dashboard](https://github.com/hummingbot/dashboard)
- [OctoBot](https://github.com/Drakkar-Software/OctoBot)
- [Plotly Dash Technical Charting](https://github.com/plotly/dash-technical-charting)
- [Base Trading Dashboard](https://github.com/dang-trung/base-trading)
- [Dash TradingView Component](https://github.com/tysonwu/dash-tradingview)
- [TradingView Lightweight Charts](https://www.tradingview.com/scripts/candlestick/)
- [Stock Portfolio Grafana Dashboard](https://grafana.com/grafana/dashboards/15956-stock-portfolio/)
- [Freqtrade Grafana Solution](https://github.com/thraizz/freqtrade-dashboard)
- [QuantConnect Backtest Results](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results)
- [AI-Predictor](https://github.com/Son930/AI-Predictor)
- [HKUDS AI-Trader](https://github.com/HKUDS/AI-Trader)
- [Grafana Prometheus Getting Started](https://grafana.com/docs/grafana/latest/fundamentals/getting-started/first-dashboards/get-started-grafana-prometheus/)
- [Cryptohopper Dashboard Docs](https://docs.cryptohopper.com/docs/trading-bot/dashboard/)
- [Hummingbot Monitor](https://github.com/afansky/hummingbot-monitor)
- [Streamlit Algo Trading Dashboard (Medium)](https://jaydeep4mgcet.medium.com/algo-trading-dashboard-using-python-and-streamlit-live-index-prices-current-positions-and-payoff-f44173a5b6d7)
- [Real-Time Forex Dashboard with Streamlit (Medium)](https://medium.com/data-science-collective/building-a-real-time-forex-dashboard-with-streamlit-and-websocket-56a14a985f42)
- [Alpaca Financial Data Streaming](https://alpaca.markets/learn/financial-data-streaming-alpaca-streamlit)
- [RSI-bot Streamlit Dashboard](https://github.com/Ajay-Maury/RSI-bot)
- [TradingAgents Dashboard](https://github.com/jiwoomap/TradingAgents-Dashboard)
- [AI-Predictor with React/Vite](https://github.com/Son930/AI-Predictor)
- [Cryptohopper Documentation](https://docs.cryptohopper.com/docs/trading-bot/dashboard/)
- [FlowHunt AI Trading Dashboard](https://www.flowhunt.io/flowhunt-ai-trading-bot/)
