# Risk Management and Monitoring for Live Trading

## Summary

Live trading is chaotic: orders get rejected, fills slip, APIs crash, and markets move in unexpected ways. Risk controls prevent catastrophic losses. Monitoring gives visibility into what's happening and what's broken. This survey covers hardened risk checks (position limits, kill-switches, exposure caps), monitoring stacks (Prometheus + Grafana + Sentry), and alerting channels (Telegram, Slack, PagerDuty). The goal is: catch problems within seconds, not hours, and enforce limits automatically.

## Risk Controls (Ordered by Criticality)

### Level 1: Position Limits (Prevent Fat Fingers)

**Max position size (absolute):**
```python
if order.qty * order.price > portfolio.cash * 0.05:  # Max 5% of portfolio per symbol
    reject_order("Position too large")
```

**Max position count:**
```python
if len(open_positions) >= 50:  # Don't hold more than 50 symbols
    reject_order("Position count limit reached")
```

**Max sector concentration:**
```python
tech_exposure = sum(pos.value for pos in open_positions if pos.symbol in tech_symbols)
if tech_exposure > portfolio.value * 0.3:  # Max 30% in tech
    reject_order("Sector concentration limit exceeded")
```

**Why:** A typo submitting 1000 shares instead of 10 could blow up the account. Limits prevent this.

---

### Level 2: Daily Loss Halt (Kill-Switch)

**Kill-switch logic:**
```python
realized_pnl_today = sum(fills_today.profit)
if realized_pnl_today < -portfolio.value * 0.05:  # Lost 5% today
    HALT_ALL_TRADING = True
    alert("Kill-switch: Daily loss limit exceeded. Manual review required.")
```

**Why:** Protects against cascading losses (bad day → desperate trades → worse day).

**Trigger threshold:** 2–5% of portfolio depending on strategy volatility.

**Recovery:** Requires operator manual reset (not automatic). Prevents "strategy spiraling" at 2 AM.

---

### Level 3: Max Drawdown Halt

**Watermark tracking:**
```python
peak_portfolio_value = max(historical_portfolio_values)
current_portfolio_value = current_cash + sum(pos.current_value)
drawdown = (current_portfolio_value - peak_portfolio_value) / peak_portfolio_value

if drawdown < -0.20:  # 20% drawdown from peak
    HALT_ALL_TRADING = True
    alert("Max drawdown reached. Halting.")
```

**Why:** Protects against systematic losses (broken strategy, regime change).

**Typical threshold:** 10–25% depending on strategy.

---

### Level 4: Order Timeout

**Track order age:**
```python
for order in open_orders:
    if (time.time() - order.submitted_at) > 300:  # 5 minutes
        broker.cancel_order(order.id)
        alert(f"Order {order.id} timed out. Cancelled.")
```

**Why:** Prevents stuck orders; ensures stale orders don't suddenly fill at bad prices.

---

### Level 5: Slippage Watchdog

**Post-fill check:**
```python
expected_fill = order.price  # Signal price
actual_fill = fill.price
slippage = abs(actual_fill - expected_fill) / expected_fill

if slippage > 0.01:  # 1% slippage (abnormal)
    alert(f"Unusual slippage: {slippage:.2%} on {fill.symbol}")
```

**Why:** Alerts if fills degrade suddenly (exchange outage, bad liquidity).

---

## Monitoring Stack

### Prometheus + Grafana

**Metrics exported by strategy (every 10 seconds):**
```python
from prometheus_client import Counter, Gauge, start_http_server

portfolio_value = Gauge('portfolio_value', 'Current portfolio value')
realized_pnl = Gauge('realized_pnl_today', 'P&L realized today')
open_positions_count = Gauge('open_positions_count', 'Number of open positions')
orders_placed_total = Counter('orders_placed_total', 'Total orders submitted')
orders_rejected_total = Counter('orders_rejected_total', 'Total orders rejected by risk checks')
order_latency_seconds = Histogram('order_latency_seconds', 'Order submission latency')

# In main loop:
portfolio_value.set(current_portfolio_value)
realized_pnl.set(calc_realized_pnl_today())
open_positions_count.set(len(positions))

start_http_server(8080)  # Prometheus scrapes http://localhost:8080/metrics
```

**Prometheus scrape (every 9 seconds):**
```yaml
global:
  scrape_interval: 9s
  evaluation_interval: 9s

scrape_configs:
  - job_name: 'strategy'
    static_configs:
      - targets: ['localhost:8080']
```

**Grafana dashboard:**
```
┌─────────────────────────────────────────┐
│ Portfolio Value: $97,453 (+2.3% today)  │
├─────────────────────────────────────────┤
│ Realized P&L: +$2,231                   │
│ Unrealized P&L: -$120                   │
│ Max Drawdown: -3.2%                     │
├─────────────────────────────────────────┤
│ Open Positions: 5                       │
│ Open Orders: 2                          │
│ Orders Placed (24h): 47                 │
│ Orders Rejected: 0                      │
├─────────────────────────────────────────┤
│ [Chart: Portfolio Value over 30 days]   │
│ [Chart: P&L by Hour]                    │
│ [Chart: Order Latency Percentiles]      │
└─────────────────────────────────────────┘
```

---

### Sentry (Exception Tracking)

**Integrate into strategy:**
```python
import sentry_sdk

sentry_sdk.init("https://<key>@sentry.io/<project>", 
                environment="production")

try:
    signal = compute_signal(market_data)
    qty = compute_position_size(signal, portfolio)
    order = broker.submit_order(symbol, qty, side)
except Exception as e:
    sentry_sdk.capture_exception(e)
    alert(f"Strategy exception: {e}")
```

**Benefits:**
- Automatic traceback capture.
- Grouping of similar errors (helps identify patterns).
- Release tracking (which code version caused the error?).

---

### Structured Logging (JSON)

**Log every critical event:**
```python
import logging
import json

logger = logging.getLogger('trading')

# Structured logs
logger.info(json.dumps({
    'event': 'order_submitted',
    'symbol': 'AAPL',
    'qty': 100,
    'side': 'buy',
    'timestamp': time.time(),
    'order_id': order.id,
    'broker': 'alpaca'
}))

logger.error(json.dumps({
    'event': 'order_rejected',
    'reason': 'Position size limit exceeded',
    'symbol': 'TSLA',
    'timestamp': time.time()
}))
```

**Feed to Loki (log aggregation):**
```yaml
# Loki config
scrape_configs:
  - job_name: trading
    static_configs:
      - targets:
          - localhost
        labels:
          job: strategy
          __path__: /var/log/trading/*.log
```

**Query in Grafana:** `{job="strategy"} | json | event="order_rejected"`

---

## Alerting Channels

### Telegram Bot (Recommended for Small Teams)

**Setup (Python):**
```python
import requests

TELEGRAM_TOKEN = "123456:ABC..."
TELEGRAM_CHAT_ID = "987654321"

def alert_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': message})

# In strategy:
alert_telegram("Kill-switch activated: Daily loss > 5%")
alert_telegram(f"Order filled: 100 AAPL @ $150.23 (P&L: +$50)")
```

**Cost:** Free.

**Latency:** ~1 second.

**Reliability:** High.

---

### Slack Webhook

**Setup:**
```python
import requests

SLACK_WEBHOOK = "https://hooks.slack.com/services/..."

def alert_slack(message):
    requests.post(SLACK_WEBHOOK, json={'text': message})
```

**Cost:** Free (if Slack workspace exists).

**Latency:** ~1 second.

---

### PagerDuty (For Teams)

**Setup:**
```python
from pdpyras import APISession

session = APISession(token=PAGERDUTY_TOKEN)

def alert_pagerduty(incident_title, incident_body):
    session.post('/events/v2/enqueue', json={
        'routing_key': ROUTING_KEY,
        'event_action': 'trigger',
        'payload': {'summary': incident_title, 'details': incident_body}
    })
```

**Cost:** $49+/month/user.

**Latency:** ~2 seconds.

**Benefit:** Escalation (if you don't ack in 5 min, alert manager; if manager doesn't ack, page team).

---

## Reconciliation Job (Catch Bugs Early)

**Hourly job (cron):**
```python
def reconcile():
    """Ensure our ledger matches broker's."""
    
    # Get our open orders from database
    our_orders = db.query("SELECT * FROM orders WHERE status='open'")
    
    # Get broker's open orders
    broker_orders = broker.get_open_orders()
    
    # Compare
    our_order_ids = {o.id for o in our_orders}
    broker_order_ids = {o.id for o in broker_orders}
    
    missing_in_broker = our_order_ids - broker_order_ids
    if missing_in_broker:
        alert(f"Orders in our ledger but not broker: {missing_in_broker}")
    
    extra_in_broker = broker_order_ids - our_order_ids
    if extra_in_broker:
        alert(f"Orders in broker but not our ledger: {extra_in_broker}")
    
    # Reconcile positions
    our_positions = db.query("SELECT symbol, qty FROM positions")
    broker_positions = broker.get_positions()
    
    for symbol, qty in our_positions:
        broker_qty = broker_positions.get(symbol, 0)
        if qty != broker_qty:
            alert(f"Position mismatch: {symbol} (ours: {qty}, broker: {broker_qty})")
    
    log("Reconciliation complete")
```

---

## Architectural Takeaways for sleep-trading

1. **Risk checks are binary.** Order is approved or rejected. No gray zone.

2. **Kill-switch requires manual reset.** Prevents strategy from "trying harder" after a bad day (common failure mode).

3. **Monitor latency, not just P&L.** If order submission latency jumps from 100ms to 5s, your edge erodes. Alert on p99 latency > 500ms.

4. **Alert on actionable events.** "Strategy lost $100" → operator ignores. "API connection down" or "Reconciliation mismatch" → operator acts.

5. **Reconcile hourly.** Catches bugs (mismatched ledger), broker glitches, and network corruption early.

6. **Separate monitoring from alerting.** Grafana for human inspection; Telegram/Slack for urgent alerts. Different audiences.

7. **Log everything as JSON.** Enables querying (Loki, ELK) and auditing. CSV logs are unsearchable.

## Sources

- [Monitoring with Prometheus and Grafana - Medium](https://medium.com/@virgilliayeala/building-a-complete-monitoring-stack-using-prometheus-grafana-and-sentry-d452bdbfd67b)
- [Prometheus configuration - Prometheus.io](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Alerta integrations - Alerta docs](https://docs.alerta.io/integrations.html)
- [PagerDuty Slack integration - PagerDuty](https://support.pagerduty.com/main/docs/slack-integration-guide)
