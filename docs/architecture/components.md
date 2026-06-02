# Component interactions

Three diagrams. Top-down: system view → data-layer internals → live-vs-backtest swap. Boxes labelled `(planned)` aren't built yet; everything else corresponds to code on disk today.

Cross-references:
- [`data-module.md`](./data-module.md) — full prose for the data layer.
- [`../plan/data.md`](../plan/data.md) — eight-layer abstraction plan.
- [`../plan/dashboard.md`](../plan/dashboard.md) — UI plan.

## 1. System overview

```mermaid
flowchart LR
    classDef planned stroke-dasharray:4 4,fill:#fafafa,color:#666
    classDef built fill:#eef,stroke:#447

    subgraph Vendors["External vendors"]
        Alpaca["Alpaca"]:::planned
        CCXT["CCXT exchanges"]:::planned
        OANDA["OANDA"]:::planned
        IBKR["IBKR"]:::planned
        Polygon["Polygon"]:::planned
    end

    subgraph DataSvc["Data service (src/data)"]
        direction TB
        SvcShell["aiohttp server<br/>healthz · hello · ws"]:::built
        Adapters["Vendor adapters"]:::planned
        Pipeline["Middleware pipeline"]:::planned
        Bus["In-process bus"]:::planned
        TS[("TimescaleDB")]:::planned
        PQ[("Parquet archive")]:::planned
    end

    subgraph Consumers
        Dashboard["Dashboard<br/>(src/dashboard)"]:::built
        Strategy["Strategy engine"]:::planned
        Risk["Risk gate"]:::planned
        Execution["Execution / OMS"]:::planned
        Backtest["Backtest driver"]:::planned
    end

    Vendors -->|WS / REST| Adapters
    Adapters --> Pipeline
    Pipeline --> Bus
    Pipeline --> TS
    TS -.->|cold tier| PQ

    Bus --> SvcShell
    TS --> SvcShell

    SvcShell <-->|WS + REST| Dashboard
    SvcShell <-->|DataClient| Strategy
    SvcShell <-->|DataClient| Backtest

    Strategy --> Risk
    Risk --> Execution
    Execution -->|orders| Vendors
```

The `aiohttp server` box is what runs today (`src/data/main.py`). Everything around it is on the roadmap.

## 2. Data layer internals (the eight abstractions)

```mermaid
flowchart LR
    classDef proto fill:#fff5e0,stroke:#b58900
    classDef impl fill:#eef,stroke:#447
    classDef store fill:#efe,stroke:#484

    subgraph L4["L4 · Source"]
        SrcProto["«Source»"]:::proto
        Vendor["VendorAdapter"]:::impl
        Replay["ReplayAdapter"]:::impl
        Mock["MockSource"]:::impl
    end

    subgraph L6["L6 · Middleware"]
        Dedup["DedupMiddleware"]:::impl
        Gap["GapFillerMiddleware"]:::impl
        BarAgg["BarAggregator"]:::impl
        Filter["Symbol/ChannelFilter"]:::impl
    end

    subgraph L5["L5 · Sink"]
        SinkProto["«Sink»"]:::proto
        Bus["BusPublisher"]:::impl
        TSW["TimescaleWriter"]:::impl
        Metrics["MetricsSink"]:::impl
        Fanout["FanoutSink"]:::impl
    end

    subgraph L7["L7 · Client"]
        DC["DataClient"]:::impl
    end

    subgraph L8["L8 · Storage seams"]
        ReaderProto["«HistoricalReader»"]:::proto
        TSR["TimescaleReader"]:::impl
        PQR["ParquetReader"]:::impl
    end

    subgraph L1L2L3["L1–L3 · Cross-cutting"]
        Events["Event types<br/>Tick · Trade · Bar · OrderbookUpdate"]
        Tax["Symbol · Venue · Channel"]
        Clock["Clock<br/>Live · Replay · Fixed"]
    end

    Vendor -.implements.-> SrcProto
    Replay -.implements.-> SrcProto
    Mock   -.implements.-> SrcProto

    Bus     -.implements.-> SinkProto
    TSW     -.implements.-> SinkProto
    Metrics -.implements.-> SinkProto
    Fanout  -.implements.-> SinkProto

    TSR -.implements.-> ReaderProto
    PQR -.implements.-> ReaderProto

    SrcProto -->|events| Dedup --> Gap --> BarAgg --> Filter -->|events| Fanout
    Fanout --> Bus
    Fanout --> TSW
    Fanout --> Metrics

    Bus -->|subscribe| DC
    ReaderProto -->|history| DC
    Clock --> DC

    DC -->|stream / history| Caller["Strategy · Features · Dashboard"]:::impl

    Events -.types.-> SrcProto
    Events -.types.-> SinkProto
    Events -.types.-> ReaderProto
    Tax -.types.-> SrcProto
    Tax -.types.-> DC
```

Solid arrows are runtime data flow. Dotted arrows are type / protocol references. The same `DataClient` is the only consumer-facing surface; whatever sits behind the bus and reader can change without touching strategies.

## 3. Live vs backtest — same code, different wiring

```mermaid
flowchart LR
    classDef live fill:#eef,stroke:#447
    classDef back fill:#fef,stroke:#844
    classDef shared fill:#efe,stroke:#484

    subgraph LiveMode["Live mode"]
        VA["VendorAdapter"]:::live
        BUS1["Bus"]:::live
        TS1[("TimescaleDB")]:::live
        LC["LiveClock"]:::live
    end

    subgraph BackMode["Backtest mode"]
        RA["ReplayAdapter (Parquet)"]:::back
        BUS2["Bus"]:::back
        PQR["ParquetReader"]:::back
        RC["ReplayClock"]:::back
    end

    subgraph SharedCode["Same code on both sides"]
        DC["DataClient"]:::shared
        Strat["strategy.on_event(...)"]:::shared
    end

    VA -->|live ticks/bars| BUS1 --> DC
    TS1 -->|history| DC
    LC --> DC

    RA -->|recorded events at speed| BUS2 --> DC
    PQR -->|history| DC
    RC --> DC

    DC --> Strat
```

The strategy code path doesn't branch on mode. The choice happens once at startup — which `Source`, which `HistoricalReader`, which `Clock` — and after that the world looks identical to the strategy.
