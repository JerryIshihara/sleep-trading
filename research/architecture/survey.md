# Architecture Survey

## Summary

Algorithmic trading systems require a choice between two fundamental architectural patterns: event-driven (pub/sub with message queues, enables real-time responsiveness) and request/response (synchronous APIs, simpler initially but harder to scale). For small teams, the consensus has shifted toward modular monoliths with targeted microservices at edges, avoiding the 10+ developer threshold where microservices complexity becomes justified. A single VPS or Docker Compose host running a cohesive system beats distributed complexity for teams under 5 engineers.

## Key Architecture Patterns

**Event-Driven Architecture**
- Market tick arrives → published to message bus → multiple consumers (signal, risk, monitoring) react asynchronously
- Enables decoupling and resilience; one failed component doesn't block the pipeline
- Natural fit for live trading where every millisecond matters
- Examples: Kafka-based pipelines, RabbitMQ event streams
- Backtesting equivalently uses event loops to replay historical ticks

**Request/Response (Synchronous)**
- Strategy polls for data, submits order via REST, waits for confirmation
- Simpler debugging; harder to scale beyond a few strategies
- Sufficient for low-frequency (hourly/daily) systems
- Risk: correlated failures if external API latencies spike

**Monolith vs. Microservices**
- Monolith: single codebase, shared database, easier to reason about state
- 2025 industry data: teams under 10 developers regret microservices; monoliths reduce costs 25%
- Recommended for sleep-trading: modular monolith (clean layering) + serverless for scheduled research jobs

## High-Level System Layouts

### Layout 1: Event-Driven Single Host (Recommended for Small Teams)
```
┌─────────────────────────────────────────────────┐
│  Broker APIs          Market Data Feeds          │
│  (Alpaca, IBKR)       (Polygon, Tiingo)         │
└──────────┬─────────────────────┬────────────────┘
           │                     │
        ┌──────────────────────────────┐
        │   Data Ingestion Layer       │
        │ (Async drivers, retries)     │
        └──────────┬───────────────────┘
                   │
        ┌──────────▼───────────────────┐
        │    Message Bus (Kafka)       │
        │  (or RabbitMQ, Redis)        │
        └──────────┬───────────────────┘
    ┌───────────┬──┴──┬──────────┬──────────┐
    ▼           ▼     ▼          ▼          ▼
┌─────────┐ ┌──────┐ ┌────────┐ ┌──────┐ ┌─────┐
│ Feature │ │Strat │ │ Risk & │ │Exec  │ │Obs  │
│ Calc    │ │Logic │ │Position│ │Order │ │&Mon │
└─────────┘ └──────┘ └────────┘ └──────┘ └─────┘
    │          │         │         │        │
    └──────────┴─────────┴─────────┴────────┘
              │
        ┌─────▼──────────────────┐
        │ Time-Series DB         │
        │ (TimescaleDB/ClickHouse)
        │ + Order State Cache    │
        └────────────────────────┘
```

### Layout 2: Modular Monolith with Serverless Extensions
```
┌──────────────────────────────────────────────────┐
│         Core Monolith (VPS/Docker)               │
│  ┌────────────────────────────────────────────┐  │
│  │ Data Ingestion → Signals → Strategy → Risk │  │
│  │         + Live Order Management            │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
   │                        │                  │
   │                        │                  │
┌──▼──────────┐   ┌─────────▼────────┐  ┌────▼────────┐
│ Postgres +  │   │ Scheduled Jobs   │  │ Monitoring  │
│ TimescaleDB │   │ (Backtest, Opt)  │  │ Dashboards  │
│ (Persistent)    │ [AWS Lambda/GCP]  │  │ (Grafana)   │
└─────────────┘   └──────────────────┘  └─────────────┘
```

## Architectural Takeaways for sleep-trading

- **Start with event-driven, single-host monolith.** Message queues (Kafka/Redis) vs. synchronous: the former wins for real-time, low-latency needs. At 1–2 person teams, operational simplicity beats distributed sophistication.

- **Separate hot path (execution) from cold path (research).** Live trading runs on a dedicated, minimal-dependency server. Strategy research, backtesting, and ML model training run asynchronously in notebooks or Lambda jobs, feeding results back as config.

- **Decouple via message boundaries, not API gateways.** Publish market ticks, signals, and fills to a bus; let risk checks, execution, and monitoring consume independently. Failure of one consumer (e.g., a logging service) should not block orders.

- **Avoid microservices unless you have 10+ backend engineers.** A single Postgres + Python Flask/FastAPI process handles data ingestion, strategy, risk, and order submission. Scale horizontally only when you hit a single-host ceiling (rare in small-team trading).

- **Use async/await and Python asyncio** (or Tokio in Rust) for non-blocking I/O; avoids thread overhead and GIL contention. Pairs naturally with event-driven logic.

- **Shared state must be explicit.** Postgres or Redis stores order state, position inventory, and P&L. No in-memory-only counters unless backed by logs. Enables recovery and multi-worker resilience.

## Sources

- [Algorithmic Trading System Architecture — Stuart Gordon Reid (TuringFinance)](https://www.turingfinance.com/algorithmic-trading-system-architecture-post/)
- [Event-Driven vs Request-Driven Architecture — Medium](https://medium.com/devdotcom/event-driven-architecture-vs-request-response-a-practical-comparison-aadc68efea0c)
- [Event-Driven Backtesting with Python — QuantStart](https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/)
- [Monolith vs Microservices in 2025 — Pawel Piwosz (Medium)](https://medium.com/@pawel.piwosz/monolith-vs-microservices-2025-real-cloud-migration-costs-and-hidden-challenges-8b453a3c71ec)
- [Microservices-Based Algorithmic Trading System — GitHub](https://github.com/saeed349/Microservices-Based-Algorithmic-Trading-System)
