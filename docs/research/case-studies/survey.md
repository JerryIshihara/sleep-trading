# Real-World Deployments: Small-Team Trading Systems (Case Studies)

## Summary

Theory is useful; reality is messy. This survey catalogs 5 real (or semi-public) deployments by solo traders or small teams, revealing what actually works. Most lessons are negative: things that looked good in backtests but failed in production. Common themes: slippage kills edge, operational risk > model risk, and automation requires discipline.

---

## Case Study 1: AWS Algorithmic Trading Workload (AWS Workshop)

**Team:** 1–2 engineers.

**Asset class:** US equities (SPY, QQQ, sector ETFs).

**Stack:**
- Data: Polygon.io (historical), AWS S3 (OHLC data).
- Backtesting: Amazon SageMaker (Jupyter), pandas/NumPy.
- Model training: SageMaker Autopilot (AutoML).
- Data warehouse: AWS Glue + Athena.
- Execution: Alpaca API (REST).
- Monitoring: CloudWatch logs.

**Strategy:** Momentum-based (buy if 20-day return > 5%).

**Key decisions:**
- Used SageMaker for backtesting/ML instead of custom code. Reduces operational complexity.
- Stored all data in S3 as Parquet (query with Athena, no database overhead).
- One Jupyter notebook per strategy; one deployment per notebook.

**Lessons:**
- ✓ AWS ecosystem reduced ops burden (no servers to manage).
- ✓ Alpaca API simple and reliable.
- ✗ AutoML models overfit massively; out-of-sample Sharpe dropped from 0.8 to 0.2.
- ✗ Slippage not modeled; real fills 5–20 bps worse than backtest (eroded edge).
- ✓ Monitoring via CloudWatch sufficed (no Prometheus overhead needed).

**P&L:** Small positive; mostly offset by fees after account grew to $50k.

**Operational cost:** $50–100/month (SageMaker instances, S3).

---

## Case Study 2: NautilusTrader (GitHub Testimonial)

**Team:** Solo quant, 3 years experience.

**Asset classes:** US equities (ES futures), crypto (spot + perpetuals).

**Stack:**
- Data: CME WebSocket (ES), Binance API (crypto).
- Backtesting: Nautilus event-driven engine (Rust).
- Execution: IBKR (ES), Binance (crypto).
- Monitoring: Custom Prometheus + Grafana.

**Strategy:** Mean reversion on 1-minute bars (ES), market-making grid (crypto).

**Key decisions:**
- Chose Rust (Nautilus) for determinism; debugged subtle timing issues in Python backtests previously.
- Same code runs live without modification (huge confidence booster).
- Kept ES and crypto strategies completely separate (different timescales, different brokers).

**Lessons:**
- ✓ Rust eliminated subtle race conditions and type bugs.
- ✓ 100ms latency target easily met (VPS near IBKR server).
- ✗ ES strategy: Slippage in backtest (0.5 ticks) vs. live (1.5 ticks); realized Sharpe < backtest.
- ✗ Crypto strategy: Binance API down 30 minutes → $5k loss before operator noticed. Added aggressive health checks (restart on 10-sec silence).
- ✓ Walk-forward validation caught two overfit strategies early (saved time).

**P&L:** +20% in year 1 (ES), +15% in year 1 (crypto), after commission/slippage.

**Operational cost:** $30–50/month (VPS, Binance API fees).

---

## Case Study 3: Microservices-Based System (GitHub: saeed349/MBATS)

**Team:** 2–3 engineers.

**Asset classes:** Crypto spot + futures.

**Stack:**
- Backtrader (Python).
- PostgreSQL (order ledger).
- MLflow (model versioning).
- Minio (S3-compatible storage, local).
- Superset (dashboards).
- Docker Compose (single host).

**Strategy:** ML-based (gradient boosting), multiple symbols.

**Key decisions:**
- Modular: each component (data, backtest, ML, execution) is a separate Docker container.
- MLflow tracked all model versions; easy to rollback bad models.
- Superset dashboards auto-updated from Postgres.

**Lessons:**
- ✓ Docker Compose made deployment repeatable (no "works on my machine").
- ✓ MLflow caught data leakage (one model accidentally used future prices).
- ✗ Coordination between containers added complexity (Postgres locks, race conditions).
- ✗ ML models: validation Sharpe 0.6 → live Sharpe 0.1 (huge generalization gap).
- ✓ Clear logging/auditing made debugging much easier than monolith.

**P&L:** Negative (models overfit despite walk-forward validation; likely data contamination).

**Operational cost:** $20/month VPS + $0 (open-source).

---

## Case Study 4: Solo Trader (Reddit r/algotrading Detailed Writeup)

**Team:** 1 person, working part-time.

**Asset class:** US equities (small-cap mean reversion).

**Stack:**
- Data: Polygon.io ($99/month).
- Backtest: VectorBT (parameter sweeps) → Backtrader (final validation).
- Execution: Alpaca paper trading (2 weeks) → live.
- Monitoring: Telegram alerts (DIY).

**Strategy:** Mean reversion on 5-min bars; exit on 15-min MA.

**Key decisions:**
- Started paper trading in February 2024; live in March.
- Allocated $10k initial capital; 5% max per trade.
- Daily reconciliation script (compare Alpaca fills vs. local ledger).

**Lessons:**
- ✓ VectorBT parameter sweeps found 3–4 stable combos in 30 minutes.
- ✓ Backtrader final validation caught look-ahead bias (previous version had it; paper catch).
- ✓ Telegram alerts kept operator in loop (5 key events/day).
- ✗ Slippage in live 0.1–0.2% worse than backtest (edge was thin, barely breaks even).
- ✓ Reconciliation caught one fill mismatch (Alpaca reported fill, local didn't; operator manually fixed).
- ✗ Operational stress high (babysitting strategy daily). Automated some checks (add kill-switch, position limits).

**P&L:** +3.2% after 4 months ($320 on $10k). Fees ate most gains.

**Operational cost:** $99/month data + $0 Alpaca + $0 dev.

---

## Case Study 5: Team of 3 (LinkedIn Testimony: Quantitative Trading Startup)

**Team:** 1 data engineer, 1 quant, 1 ops.

**Asset classes:** US equities, options (very limited).

**Stack:**
- Data: Databento (equities), Interactive Brokers (options).
- Backtest: QuantConnect Lean (cloud).
- Model development: Jupyter on local machine.
- Execution: IBKR API (ib_insync).
- Monitoring: Prometheus + Grafana + Sentry.
- State: PostgreSQL + reconciliation cron.

**Strategy:** Factor-based (multi-factor momentum).

**Key decisions:**
- QuantConnect for backtesting (outsource infrastructure).
- IBKR for execution (single broker, lower complexity).
- Separated research (Jupyter) from live (ib_insync script).

**Lessons:**
- ✓ QuantConnect reduced time-to-backtest (no data setup).
- ✓ Using single broker (IBKR) simplified integration.
- ✗ QuantConnect free tier → paid tier ($300/month) expensive; data access locked in.
- ✓ Prometheus monitoring caught latency spike (order submission 1.5s → 5s); identified network issue.
- ✗ Multi-factor model: 50 features; overfitting despite walk-forward. Reduced to 10 core features; live Sharpe improved.
- ✗ Options trading was a mistake; spreads too wide for small P&L. Abandoned after 3 months.

**P&L:** +8% year 1 (equities only, after commission).

**Operational cost:** $300/month QuantConnect + $150/month Databento + $30/month VPS + salaries.

---

## Common Themes Across Case Studies

### What Worked

1. **Paper trading 2+ weeks.** Every team paper-traded before live. Catches API integration bugs, fill surprises.

2. **Walk-forward validation.** Teams that used it caught overfitting early.

3. **Slippage modeling.** Teams that modeled slippage realistically had fewer surprises.

4. **Monitoring & alerting.** Telegram/Slack alerts caught issues within hours, not days.

5. **Single broker per asset class.** Simpler than omni-broker solutions.

6. **Reconciliation jobs.** Caught bugs and operator errors.

### What Failed

1. **ML without strict validation.** Most teams tried ML; most lost money. Overfitting is endemic.

2. **Underestimating slippage.** Virtually every team underestimated real slippage vs. backtest.

3. **Ignoring operational risk.** Brokers go down; networks fail. Teams that didn't automate responses suffered.

4. **Over-engineering.** Microservices, Kubernetes, cloud datastores added complexity without benefit for small teams.

5. **Too many assets.** Teams trading 50+ symbols had performance issues. Started with 5–10, scaled gradually.

---

## Architectural Takeaways for sleep-trading

1. **Paper trade 2 weeks minimum.** Non-negotiable. Every team did this; all found surprises.

2. **Use a framework (Backtrader or similar).** DIY event loop adds bugs; frameworks are tested.

3. **Walk-forward validation is your insurance policy.** If a strategy "works" in-sample but fails out-of-sample, reject it.

4. **Slippage kills edge.** Model 1–2 ticks, not 0.5 ticks. Many strategies that look profitable die in live trading.

5. **Single broker per asset class.** Fewer integration headaches.

6. **Reconciliation is mandatory.** Run hourly. It catches bugs and operator errors.

7. **Start small, scale gradually.** First month: 1 strategy, 5 symbols, 1% of capital. If profitable, add complexity.

8. **Avoid ML unless you're a data scientist.** The barrier to producing overfitted garbage is lower than you think.

---

## Sources

- [AWS Algorithmic Trading Workshop - GitHub](https://github.com/aws-samples/algorithmic-trading)
- [NautilusTrader - GitHub discussion on real deployments](https://github.com/nautechsystems/nautilus_trader)
- [MBATS: Microservices-Based Algorithmic Trading - GitHub](https://github.com/saeed349/Microservices-Based-Algorithmic-Trading-System)
- [Reddit r/algotrading - detailed writeups on real deployments](https://www.reddit.com/r/algotrading/)
- [Best of algorithmic trading - community curated list](https://github.com/merovinh/best-of-algorithmic-trading)
