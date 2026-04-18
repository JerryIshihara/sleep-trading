# Trading Brokers & Execution APIs: Asset Coverage, Pricing, and Live Trading Support

## Summary

A broker is your gateway to liquidity. The choice of broker shapes which asset classes you can trade, your fees, and your latency profile. This survey catalogs retail and professional brokers offering API access, with emphasis on paper trading (essential for validation), asset class support (equities, options, futures, crypto, FX), and API design (REST vs WebSocket vs FIX). For a small team spanning multiple asset classes, a hybrid broker strategy (one for equities, one for crypto, one for futures) is often cheaper and faster than a single omnibus broker.

## Equities (US & International)

### Alpaca
- **Asset classes:** US equities, ETFs, options (limited), crypto.
- **Paper trading:** Yes, identical API to live.
- **API style:** REST + WebSocket + fix protocol (custom).
- **Commission:** Commission-free stocks and ETFs; options: $0.65/contract.
- **Rate limits:** 200 req/min (free), 5000 req/min (premium).
- **Key feature:** Purpose-built for algo traders; paper and live are code-identical.
- **Latency:** ~100–200ms (cloud-hosted).
- **Best for:** Solo traders, small teams, US equities + crypto.

### Interactive Brokers (IBKR)
- **Asset classes:** US equities, options, futures, forex, bonds, commodities.
- **Paper trading:** Yes, Paper Trading mode within TWS.
- **API style:** Trader Workstation (TWS) API + Python (ib_insync, async/sync).
- **Commission:** $0.50–$1 per contract (futures); $0.005 per share (stocks, min $1).
- **Rate limits:** API data lines shared; typically 100–200 simultaneous subscriptions.
- **Key feature:** Most comprehensive asset coverage. Institutional-grade. Steep learning curve.
- **Latency:** ~50–150ms if co-located; worse over internet.
- **Best for:** Multi-asset traders; futures and options professionals.

### Tradier
- **Asset classes:** US equities, options, ETFs; forex via OANDA integration.
- **Paper trading:** Yes, sandbox environment.
- **API style:** REST + WebSocket.
- **Commission:** Stocks $0 (affiliate commissions rebated); options $0.65/contract.
- **Rate limits:** 500 requests/min.
- **Key feature:** Simple REST API; OAuth2 authentication; good for beginners.
- **Latency:** ~100–300ms.
- **Best for:** Developers; simple REST-first design.

### TradeStation
- **Asset classes:** US equities, options, futures.
- **Paper trading:** Yes (limited to TradeStation platform).
- **API style:** Custom TradeStation SDK (C#, EasyLanguage).
- **Commission:** $0 stocks; $0.50 per contract (futures); $0.65 options.
- **Rate limits:** Moderate.
- **Key feature:** Integrated backtesting language (EasyLanguage); proprietary.
- **Latency:** Platform-dependent.
- **Best for:** TradeStation power users; not ideal for polyglot teams.

---

## Futures (US Equities & Commodities)

### Interactive Brokers (IBKR) + ib_insync
- **Asset classes:** CME ES (S&P 500), NQ (Nasdaq), CL (crude oil), GC (gold), etc.
- **Paper trading:** Paper Trading mode.
- **API style:** TWS API (Python ib_insync).
- **Commission:** $0.50–$1 per round-turn contract.
- **Latency:** 50–150ms (internet-based).
- **Best for:** Retail futures traders; affordable; good API.

### Tradier (via Deribit integration)
- **Asset classes:** Crypto futures (Deribit).
- **API style:** REST.
- **Commission:** Variable (Deribit taker/maker fees).

---

## Cryptocurrency

### Binance
- **Asset classes:** Spot (1000+ pairs), USD Margin, Futures (USDM and COINM).
- **Paper trading:** Testnet (separate environment; not perfectly synced with live).
- **API style:** REST + WebSocket.
- **Commission:** 0.1% taker / 0.1% maker (default); volume discounts.
- **Rate limits:** 1500 orders/min; highest among major exchanges.
- **Key feature:** Highest liquidity; extensive order types.
- **Best for:** High-frequency crypto trading; liquidity-sensitive strategies.

### Coinbase Advanced Trade API
- **Asset classes:** Spot crypto (100+ pairs), USD Margin.
- **Paper trading:** Sandbox environment (free).
- **API style:** REST + WebSocket.
- **Commission:** 0.6% (default); declining with volume.
- **Rate limits:** 10–50 orders/sec (bursty).
- **Key feature:** US-regulated; strong security; beginner-friendly.
- **Best for:** US-based traders; high-conviction, lower-frequency strategies.

### Kraken
- **Asset classes:** Spot, margin, futures (Futures and Derivatives programs).
- **Paper trading:** Demo API (separate Kraken Futures testnet).
- **API style:** REST + WebSocket + FIX (professional).
- **Commission:** 0.16–0.26% (maker/taker); rising with volume.
- **Rate limits:** 15 API calls per second; WebSocket higher.
- **Key feature:** FIX support for professional traders; strong compliance.
- **Best for:** Professional-grade traders; multi-strategy setups; FIX shops.

### Bybit
- **Asset classes:** Spot, Perpetuals (USDT-M and Coin-M), Futures.
- **Paper trading:** Testnet.
- **API style:** REST + WebSocket.
- **Commission:** 0.1% (maker/taker).
- **Rate limits:** 1000 orders/min.
- **Key feature:** Growing liquidity; derivatives focus.
- **Best for:** Futures and perpetuals traders.

### OKX (OKCoin)
- **Asset classes:** Spot, margin, futures, perpetuals.
- **Paper trading:** Testnet.
- **API style:** REST + WebSocket.
- **Commission:** 0.1–0.15% (tiered).
- **Rate limits:** Moderate.
- **Best for:** Asian traders; alternative liquidity source.

---

## Foreign Exchange (FX)

### OANDA
- **Asset classes:** 140+ forex pairs; indices; commodities; metals.
- **Paper trading:** Yes (practice account, free).
- **API style:** REST (v20 API standard).
- **Commission:** Spreads only (0.5–2 pips for majors).
- **Rate limits:** 256 requests/min (free tier).
- **Key feature:** Lowest spreads for retail; simple REST API; broker + data provider combo.
- **Best for:** FX scalpers; small account holders.

### Saxo Bank / SaxoTrader API
- **Asset classes:** FX, stocks, options, futures (global).
- **API style:** REST + WebSocket.
- **Commission:** Spreads + commission (variable).
- **Best for:** Professional traders; high asset class breadth.

---

## Options (US)

### Alpaca (limited)
- **Asset classes:** US stock options.
- **Paper trading:** Yes.
- **API style:** REST.
- **Commission:** $0.65 per contract.

### IBKR
- **Asset classes:** US stock and index options.
- **Paper trading:** Yes.
- **API style:** TWS API (Python).
- **Commission:** $0.65 per contract (minimum variable).

---

## Multi-Asset Aggregators & Unified APIs

### CCXT (Crypto)
- **Coverage:** 130+ exchanges unified under one API.
- **Paper trading:** Testnet available for most exchanges.
- **API style:** Unified REST/WebSocket.
- **Cost:** Free, open-source.
- **Best for:** Crypto arbitrage; exchange-agnostic code.

---

## Architectural Takeaways for sleep-trading

1. **Paper trade first, always.** Alpaca, IBKR, Binance testnet, and Kraken demo are all free. Validate your strategy and API integration without risking capital.

2. **Choose by asset class, not by broker.**
   - **Equities:** Alpaca (simplest) or IBKR (most assets).
   - **Equities + Futures:** IBKR.
   - **Crypto spot:** Binance or Coinbase (regulate), or CCXT for multi-exchange.
   - **Crypto derivatives:** Bybit or Kraken Futures.
   - **FX:** OANDA.

3. **API matters more than commission.** Good API (REST + WebSocket, low latency, high rate limits) beats 1 basis point fee savings. Alpaca REST is simpler than IBKR TWS API.

4. **Avoid single-broker dependency.** If Alpaca has an outage, your US equity trading halts. Keep a fallback broker (IBKR for equities, Binance + Kraken for crypto).

5. **Rate limits scale linearly with order count.** 500 orders/min (Tradier) is tight for 50-symbol portfolio. Alpaca 5000 req/min (premium) is safer.

6. **Monitor broker API latency.** Cloud-hosted (Alpaca) typically 100–300ms. Direct co-location (futures) can hit 50ms. Accept the trade-off or upgrade.

7. **Use abstract broker interface.** Write code that calls submit_order(symbol, side, qty) and swap brokers without rewriting strategy code. CCXT and custom wrappers do this.

## Sources

- [IBKR Trading API - Interactive Brokers](https://www.interactivebrokers.com/en/trading/ib-api.php)
- [Alpaca API Docs](https://docs.alpaca.markets/)
- [Best brokers for algorithmic trading - BrokerChooser](https://brokerchooser.com/best-brokers/best-brokers-for-algo-trading-in-the-united-states)
- [Kraken Trading API](https://www.kraken.com/features/trading-api)
- [Coinbase Advanced Trade API - CoinAPI Blog](https://www.coinapi.io/blog/best-crypto-exchange-apis-developers-traders-2025)
- [OANDA FX API](https://www.oanda.com/foreign-exchange-data-services/en/exchange-rates-api/)
- [ib_insync - GitHub](https://github.com/erdewit/ib_insync)
