# Market Data Vendors: Coverage, Pricing, and API Characteristics

## Summary

Access to timely, accurate market data is foundational. Data quality varies by vendor, exchange, and asset class (equities, crypto, FX, futures). This survey catalogs major vendors, their free tiers, pricing models, and suitability for small teams. For equities, Alpaca and Polygon dominate. For crypto, CCXT abstracts 100+ exchanges. For FX, OANDA and TrueFX offer tick data. For futures, CME Group, IBKR, and Databento lead. The key decision: do you prioritize speed (WebSocket, co-location), cost (free or $100/month), or breadth (many symbols and history)? Most small teams should start with free tiers and upgrade only when backtesting reveals edge.

## Equities (US & International)

### Alpaca Data
- **Coverage:** US equities (NYSE, NASDAQ, ARCA), options.
- **Real-time vs delayed:** Free tier limited to IEX; Algo Trader Plus ($99/month) → all US exchanges.
- **Free tier:** 200 API calls/min, 30 WebSocket subscriptions, 15-minute delayed bars.
- **API style:** REST + WebSocket.
- **Cost:** Free (Basic) → $99/month (Algo Trader Plus).
- **Key feature:** Seamless integration with Alpaca trading API; paper trading included.

### Polygon.io
- **Coverage:** US equities, options, forex, crypto.
- **Real-time vs delayed:** Real-time ticks and aggregates with tiered access.
- **Free tier:** 5 API calls/min, EOD bars only.
- **Paid tiers:** $99–$599/month depending on symbol count and tick data.
- **API style:** REST + WebSocket.
- **Cost:** Tiered; entry at $99/month for serious backtesting.

### Tiingo
- **Coverage:** US equities (daily), forex daily.
- **Real-time vs delayed:** End-of-day bars; no real-time.
- **Free tier:** Daily bars for 500 tickers; academic free access.
- **API style:** REST.
- **Cost:** $10–$100/month if you need real-time or tick data.
- **Best for:** Academic research, end-of-day strategies.

### IEX Cloud
- **Status:** Shut down August 2024. Legacy users migrate to Alpaca or Polygon.

### Databento
- **Coverage:** US equities, options, futures (US), crypto.
- **Real-time vs delayed:** Real-time and historical tick data.
- **Free tier:** $125 in credits (good for 1–2 months of testing).
- **API style:** REST + WebSocket.
- **Cost:** $25–$300/month depending on symbols and data granularity.
- **Key feature:** Unified schema across equities, options, futures, crypto.

---

## Cryptocurrency

### CCXT
- **Coverage:** 130+ exchanges (Binance, Kraken, Coinbase, Bybit, KuCoin, OKX, Huobi, etc.).
- **Real-time vs delayed:** REST (polls) + WebSocket.Pro for real-time.
- **API style:** Unified REST/WebSocket across all exchanges.
- **Cost:** Free, open-source.
- **Key feature:** Abstract the exchange-specific quirks. One function call swaps Binance for Kraken.

### Kaiko
- **Coverage:** 150+ centralized and decentralized crypto exchanges; CME Group crypto futures via redistribution.
- **Real-time vs delayed:** Real-time ticks, Level 2 order book, trades.
- **API style:** REST + WebSocket.
- **Cost:** Professional tier $300+/month.
- **Key feature:** Institutional-grade data; used by hedge funds. Overkill for solo traders but gold standard for accuracy.

### Exchange Native WebSockets
- **Binance, Kraken, Coinbase, Bybit, OKX:** All publish free WebSocket APIs directly.
- **Rate limits:** Binance highest (1500 requests/min), Coinbase lowest (100 orders/min).
- **Cost:** Free (if you trade on the exchange).
- **Best for:** Direct trading without intermediary.

---

## Foreign Exchange (FX)

### OANDA
- **Coverage:** 38,000+ currency pairs; commodities; metals.
- **Real-time vs delayed:** Real-time tick data, minute bars, daily bars.
- **API style:** REST.
- **Cost:** Free (requires $10k account) → tiered by data latency and symbol count.
- **Key feature:** Direct broker-dealer; you can trade and pull market data from the same connection.

### TrueFX
- **Coverage:** Major pairs (EURUSD, GBPUSD, etc.) and exotic pairs.
- **Real-time vs delayed:** Tick-by-tick historical data (free download).
- **API style:** CSV download or on-demand.
- **Cost:** Free historical; real-time requires sponsorship or premium plan.
- **Best for:** Backtesting FX strategies; one of the only free tick-level sources.

### HistData
- **Coverage:** FX pairs, commodities, indices.
- **Real-time vs delayed:** Historical only (1-minute bars and ticks).
- **API style:** CSV download or API for recent data.
- **Cost:** Free for historical; $30–$100/month for new data.
- **Best for:** Quick backtest setup (MetaTrader format).

---

## Futures (US Commodities, Equity Index Futures)

### CME Group
- **Coverage:** E-mini S&P 500 (ES), E-mini Nasdaq (NQ), crude oil (CL), gold (GC), etc.
- **Real-time vs delayed:** Real-time futures and options data via JSON API.
- **API style:** WebSocket + REST.
- **Cost:** Varies; typically $395/month for top-of-book; bundled in broker subscriptions.
- **Key feature:** WebSocket streaming for top-of-book and trades.

### Interactive Brokers (IBKR)
- **Coverage:** US equity futures, options, forex, bonds via IBKR API.
- **Real-time vs delayed:** Real-time if you have a funded account; paper trading available.
- **API style:** TWS (Trader Workstation) API + Python (ib_insync).
- **Cost:** Market data subscriptions bundled with trading commission ($0.50–$1 per contract).
- **Best for:** Retail traders; low fees; easy API (ib_insync).

### Databento
- **Coverage:** CME futures tick data.
- **Real-time vs delayed:** Historical tick data + real-time (if subscribed).
- **API style:** REST + WebSocket.
- **Cost:** Tiered; $25–$300/month.

---

## Architectural Takeaways for sleep-trading

1. **Start with free tiers.** Alpaca free (IEX only), Polygon free (EOD only), CCXT (crypto). Understand your edge before paying for premium data.

2. **Bundle data with trading.** Use the broker's data API when possible (Alpaca, IBKR, Binance). Reduces vendor count and costs.

3. **Separate real-time from historical.** Backtest on historical data from your database; stream real-time from exchange WebSocket. Two different data paths.

4. **For multi-asset, pick one vendor per class:**
   - **Equities:** Alpaca (if using Alpaca broker) or Polygon.
   - **Crypto:** CCXT + direct exchange WebSockets.
   - **Futures:** IBKR (if you open an account) or Databento.
   - **FX:** OANDA (if you want to trade) or TrueFX (historical only).

5. **Validate data quality early.** Cross-check OHLC bars from two sources. High slippage in backtest → likely bad data.

6. **Don't over-subscribe.** 50 symbols at real-time is enough for a small team. Broad coverage (1000 symbols) is expensive and most will never trade.

## Sources

- [Polygon vs Alpaca vs IEX Cloud - ksred.com](https://www.ksred.com/the-complete-guide-to-financial-data-apis-building-your-own-stock-market-data-pipeline-in-2025/)
- [Alpaca Market Data API - Alpaca Docs](https://docs.alpaca.markets/docs/about-market-data-api)
- [Best Financial Data APIs - Medium](https://medium.com/@trading.dude/beyond-yfinance-comparing-the-best-financial-data-apis-for-traders-and-developers-06a3b8bc07e2)
- [Databento Pricing](https://databento.com/pricing)
- [CCXT - GitHub](https://github.com/ccxt/ccxt)
- [Kaiko Data Services](https://www.kaiko.com/)
- [OANDA FX Data Services](https://www.oanda.com/foreign-exchange-data-services/)
- [CME Group Market Data APIs](https://www.cmegroup.com/market-data/real-time-futures-and-options-data-api.html)
