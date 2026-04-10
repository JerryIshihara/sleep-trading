# Deployment Patterns for Small Trading Teams

## Summary

Deployment choices shape your operational burden and latency profile. A small team (1–5 people) must balance simplicity (fewer servers to manage) against performance (low latency). The spectrum ranges from a single VPS running a monolithic Python process, to containerized microservices on a single Docker Compose host, to Kubernetes (overkill). This survey covers realistic patterns for small teams: single-host VPS, Docker Compose on VPS, hybrid (research in cloud, execution on low-latency VPS), and serverless (scheduled jobs only).

## Pattern 1: Single VPS (Simplest)

**Architecture:**
```
VPS (DigitalOcean, Linode, AWS EC2 t3.medium)
  ├─ Python process (strategy + execution)
  ├─ PostgreSQL (orders, positions, market data)
  └─ Prometheus + Grafana (monitoring)
```

**Setup:**
1. Provision VPS (Ubuntu 20.04, 2–4 CPU, 4–8GB RAM).
2. SSH in; install Python, pip, PostgreSQL.
3. `pip install alpaca-trade-api backtrader pandas`
4. Deploy strategy as Python script (systemd service).
5. Logs → journalctl; metrics → Prometheus scrape.

**Pros:**
- Minimal operational overhead.
- All code in one process; low latency.
- Cost: ~$12–30/month (DigitalOcean, Linode).

**Cons:**
- No redundancy (VPS crashes → trading halts).
- Hard to scale (one process is CPU-bound at ~50 symbols).
- No rolling restart (deploy = stop/start, brief downtime).

**Best for:** Solo traders, 1–2 strategies, <50 symbols.

**Rough cost:** $30/month VPS + $5 PostgreSQL backup = $35.

---

## Pattern 2: Docker Compose on Single VPS (Moderate)

**Architecture:**
```
VPS
  └─ Docker Compose
      ├─ Container: Python strategy + Alpaca SDK
      ├─ Container: PostgreSQL (TimescaleDB)
      ├─ Container: Prometheus
      └─ Container: Grafana
```

**docker-compose.yml example:**
```yaml
version: '3.8'
services:
  strategy:
    build: ./strategy
    environment:
      - ALPACA_API_KEY=${API_KEY}
      - DATABASE_URL=postgres://db:5432/trading
    depends_on:
      - db
    restart: always
    ports:
      - "8080:8080"

  db:
    image: timescale/timescaledb:latest-pg14
    environment:
      - POSTGRES_PASSWORD=secret
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: always

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    restart: always

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    restart: always

volumes:
  pgdata:
```

**Deploy:**
```bash
git clone <repo>
cd trading
docker compose up -d
docker compose logs -f strategy
```

**Pros:**
- Isolated services (strategy crash doesn't kill database).
- Easy rolling restarts (`docker compose pull && docker compose up -d`).
- Version control (docker-compose.yml + Dockerfile in repo).

**Cons:**
- Single point of failure (VPS crash = total halt).
- Slightly higher latency (container overhead ~10–20ms).

**Best for:** 2–3 person teams, 2–5 strategies, 100+ symbols.

**Rough cost:** $30/month VPS + backups = $35.

---

## Pattern 3: Hybrid (Research + Execution Separation)

**Architecture:**
```
Cloud (cheap, slow)
  ├─ Jupyter (strategy research, backtesting)
  └─ S3 / ClickHouse (historical data)

Low-latency VPS (near broker co-location facility)
  ├─ Strategy engine (compiled code, minimal deps)
  ├─ PostgreSQL (order ledger, positions)
  └─ Monitoring
```

**Rationale:** Backtesting and feature engineering are CPU-intensive but latency-insensitive. Execution must be fast. Separate workloads.

**Flow:**
1. Data scientist in cloud notebooks: optimize strategy, export signal logic.
2. DevOps deploys signal logic to low-latency VPS.
3. VPS generates signals, checks risk, executes orders (<100ms latency target).
4. Daily: replay data, reconcile, upload metrics to cloud.

**Pros:**
- Optimal latency (execution close to broker).
- Cheap research tier (cloud spot instances).
- Clear separation (research team ≠ ops team).

**Cons:**
- More moving parts; network between cloud and VPS.
- Deployment pipeline more complex.

**Best for:** Growing teams (5+ people), multi-strategy, multi-asset.

**Rough cost:** $30–50/month (low-latency VPS) + $50–100/month (research cloud) = $80–150.

---

## Pattern 4: Serverless (Scheduled Jobs Only)

**Use case:** Generate signals daily; send alerts. No live order execution.

**Architecture:**
```
AWS Lambda / Google Cloud Functions
  ├─ Trigger: CloudWatch Events (daily @ 9am)
  ├─ Code: Python function
  │   ├─ Fetch market data (S3)
  │   ├─ Compute signals
  │   ├─ Save results
  │   └─ Send Slack alert
  └─ Cost: ~$1/month (free tier)
```

**Example (AWS Lambda):**
```python
import boto3
import pandas as pd

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    
    # Fetch latest data
    obj = s3.get_object(Bucket='my-bucket', Key='spy_daily.csv')
    df = pd.read_csv(obj['Body'])
    
    # Compute signal
    signal = compute_signal(df)
    
    # Save result
    s3.put_object(Bucket='my-bucket', Key='signal.json', 
                  Body=json.dumps({'signal': signal}))
    
    return {'statusCode': 200}
```

**Trigger (CloudWatch):**
```bash
aws events put-rule --name daily-signal --schedule-expression "cron(0 14 * * ? *)"
aws lambda add-permission --function-name signal-generator --principal events.amazonaws.com
```

**Pros:**
- Dirt cheap ($0–10/month).
- No server to manage.
- Auto-scaling (if 1000 symbols, parallel invocations).

**Cons:**
- Can't execute live trades (no persistent connection to broker).
- Cold start lag (first invocation: 1–3 seconds).
- Timeouts (Lambda max 15 minutes).

**Best for:** Research/backtesting automation; daily signal generation; bot alerts.

---

## Storage Patterns

### Time-Series Database (Hot Data)

**TimescaleDB:**
- PostgreSQL extension; automatic time-based partitioning.
- Good for: Order ledger, OHLC bars, recent ticks.
- Setup: `docker run -d timescale/timescaledb` on your VPS.
- Query example: `SELECT * FROM bars WHERE symbol='AAPL' AND time > NOW() - INTERVAL '30 days'`.

**ClickHouse:**
- Columnar OLAP database; fast analytics on billions of rows.
- Good for: Historical tick data, analytics.
- Setup: More involved; use managed cloud (Yandex, AWS).
- Overkill unless you have 1B+ rows/day.

### Object Storage (Cold Data)

**S3 / DigitalOcean Spaces:**
- Store historical data as Parquet or CSV.
- DuckDB can query Parquet directly (SELECT * FROM 's3://bucket/data.parquet').
- Cost: ~$5/month for 100GB.

### In-Process (Fast, Small Volume)

**DuckDB:**
- Embedded OLAP database; SQL in Python.
- Good for: Ad-hoc queries during development.
- Example: `duckdb.sql("SELECT * FROM 'spy.parquet' WHERE date > '2024-01-01'").df()`.

---

## State Management

Orders and positions are critical state. Patterns:

1. **Database-backed (safest):**
   - Before placing order: write to Postgres.
   - After fill: update status.
   - On restart: query Postgres for open orders; reconcile with broker.
   - Cost: 1–2 extra queries per trade (negligible latency impact).

2. **In-memory + log (fast but risky):**
   - Keep order state in RAM.
   - Write state changes to append-only log (journalctl or Redis).
   - On crash: replay log to recover state.
   - Risk: Log corruption = wrong state.

3. **Broker's book (simple, if reliable):**
   - Ask broker for open orders on startup.
   - Assume broker is source of truth.
   - Risk: Broker API down or slow (query can take 5 seconds).

**Recommendation for small teams:** Database-backed (pattern 1). Simple, safe, acceptable latency.

---

## Monitoring & Alerting Deployment

**Prometheus scrape config (9-second interval):**
```yaml
global:
  scrape_interval: 9s

scrape_configs:
  - job_name: 'strategy'
    static_configs:
      - targets: ['localhost:8080']
```

**Alerting rules (Grafana):**
- **High latency:** If p95_latency > 500ms, alert.
- **Kill-switch triggered:** If drawdown > 5%, alert.
- **API down:** If last_scrape_timestamp < NOW() - 1 minute, alert.

**Channels:**
- Telegram bot (low cost, low friction).
- Slack webhook (if team uses Slack).
- PagerDuty (overkill for small team).

---

## Architectural Takeaways for sleep-trading

1. **Start with single VPS + Docker Compose.** Simplest for 1–3 person teams. Minimal ops overhead.

2. **Separate research and live.** Research workload (backtesting, feature engineering) doesn't need low latency. Live execution does. Use cloud for research; VPS for execution.

3. **Use TimescaleDB for ledger state.** All orders, fills, positions in Postgres. Simple, ACID, easy to query. Accept 10ms extra latency for safety.

4. **Stateless strategy code.** Strategy function takes (market_data, portfolio_state) and returns orders. No hidden state. Makes testing, restart, and redeployment trivial.

5. **Monitor latency, not just P&L.** Tail latency (p99) matters more than mean. If p99 order latency jumps from 100ms to 5s, your edge erodes.

6. **Alert on operator action required.** Alerts for: kill-switch, API down, reconciliation failure. Alert for "strategy lost 2%" → operator ignores. Alert for "API down" → operator acts.

7. **Plan for broker failure.** Have a fallback broker API connection string ready. If Alpaca is down, switch to paper on IBKR in <5 minutes.

## Sources

- [TimescaleDB Docker - Docker Hub](https://hub.docker.com/r/timescale/timescaledb)
- [Deploy PostgreSQL DuckDB - Railway](https://railway.com/deploy/7MJ9UM)
- [How to run TimescaleDB in Docker - oneuptime](https://oneuptime.com/blog/post/2026-02-08-how-to-run-timescaledb-in-docker-with-hypertables)
- [DuckPond: Building with DuckDB - DataMethods](https://datamethods.substack.com/p/duckpond-building-a-self-hosted-multi)
- [Time-series databases comparison 2026 - sanj.dev](https://sanj.dev/post/clickhouse-timescaledb-influxdb-time-series-comparison)
