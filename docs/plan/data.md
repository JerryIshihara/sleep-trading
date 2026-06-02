# Data layer — plan

## Context

The Python engine hasn't been scaffolded. A hello-world service skeleton lives at `src/data/` — it proves the process shape (async server, `uvloop`, WebSocket) but is not a real data service. Before vendor adapters, storage, and pub/sub land, we commit to a layered abstraction so the layer stays clean: swappable vendors, same code live and backtest, unit-testable with zero network, and no vendor leakage above the adapter boundary.

## Design goals

1. **Swap any vendor without touching strategies or features.** The rest of the system never sees a vendor-shaped value.
2. **Same code paths in live and backtest.** Strategy, features, risk modules don't know which they're in.
3. **Unit-testable with zero network, zero vendor SDK.** Any layer can be pinned by a mock in the layer below it.
4. **Parallel consumers.** Dashboard, strategy, backtest driver, debug tools can all sit on the same event stream.
5. **Deterministic replay.** Given the same Parquet + same strategy + same seed, backtest is bit-reproducible.
6. **Typed errors at every seam.** No vendor exception ever escapes the adapters layer.

## Abstractions (eight layers)

### L1 — Event model
Frozen `@dataclass(slots=True)` types: `Tick`, `Trade`, `Bar`, `OrderbookUpdate`. Union `Event = Tick | Trade | Bar | OrderbookUpdate`. Every event carries `symbol: str`, `venue: str`, `ts: datetime` (venue time, tz-aware UTC), `recv_ts: datetime` (process time). `Decimal` for every price/size. Union members are disjoint — strategy code dispatches with `match`.

### L2 — Taxonomy
Naming lives here so no stringly-typed vendor bleed:
- `Symbol` — canonical form per asset class (`AAPL`, `BTC-USD`, `EUR_USD`, `ESZ5`).
- `Venue` — exchange / ECN code (`NASDAQ`, `BINANCE`), never the vendor.
- `Channel` — enum: `TICKS`, `TRADES`, `BARS_1M`, `BARS_1S`, `ORDERBOOK_L2`.
- `SymbolMap` — adapter-owned `canonical ↔ vendor` mapping, built from config or ref-data at startup.

### L3 — Clock
```python
class Clock(Protocol):
    def now(self) -> datetime: ...
```
`LiveClock` wraps `datetime.now(tz=UTC)`. `ReplayClock` advances as each event flows out of replay. **Rule:** any code that needs "now" takes a `Clock` dependency — `datetime.now()` is banned from core layers. This is what lets "last 60 seconds of ticks" windows behave identically under live and replay.

### L4 — Source
```python
class Source(Protocol):
    async def connect(self) -> None: ...
    async def subscribe(self, symbols: Sequence[Symbol], channels: Sequence[Channel]) -> None: ...
    async def unsubscribe(self, symbols: Sequence[Symbol], channels: Sequence[Channel]) -> None: ...
    def events(self) -> AsyncIterator[Event]: ...
    async def close(self) -> None: ...
```
Implementations: `VendorAdapter` (one per vendor, owns reconnect / auth / rate-limit / gap-detection); `ReplayAdapter` (Parquet or Timescale, drives the `ReplayClock`); `MockSource` (tests). **An adapter emits only normalized events. A vendor dict, enum, or exception is a bug.**

### L5 — Sink
```python
class Sink(Protocol):
    async def handle(self, event: Event) -> None: ...
    async def flush(self) -> None: ...
    async def close(self) -> None: ...
```
Implementations: `TimescaleWriter` (batched inserts), `BusPublisher` (in-process or broker), `MetricsSink`, `FanoutSink(sinks)`, `NullSink`.

### L6 — Middleware
Composable `Source → Source` transformers, stacked like decorators:
- `DedupMiddleware` — drops repeated `(symbol, venue, seq)`.
- `GapFillerMiddleware` — watches seq, emits `DataGap` or triggers `backfill`.
- `SymbolFilter` / `ChannelFilter` — narrows stream.
- `BarAggregator` — trades → bars for venues without native bars.
- `EnrichMiddleware(fn)` — generic stamp-in.

```python
source = BarAggregator("1m")(
    DedupMiddleware()(
        GapFillerMiddleware()(
            AlpacaAdapter(...))))
```

### L7 — Client
The only abstraction strategies / features / dashboard touch:
```python
class DataClient:
    def __init__(self, bus: Bus, history: HistoricalReader, clock: Clock) -> None: ...
    def stream(self, symbols, channels) -> AsyncIterator[Event]: ...
    async def history(self, symbol, channel, start, end) -> AsyncIterator[Event]: ...
    def now(self) -> datetime: ...
```
One implementation, three modes:
- Live → in-process `Bus` + `TimescaleReader` + `LiveClock`.
- Backtest → replay-fed `Bus` + `ParquetReader` + `ReplayClock`.
- Unit test → `FakeBus` + `StaticHistory` + `FixedClock`.

### L8 — Storage seams
```python
class HistoricalReader(Protocol):
    async def bars(self, symbol, venue, interval, start, end) -> AsyncIterator[Bar]: ...
    async def ticks(self, symbol, venue, start, end) -> AsyncIterator[Tick]: ...

class HistoricalWriter(Sink): pass
```
Split because the write path runs hot (fire-and-forget batched) while read path serves research / backtest / REST — very different tuning and pooling.

## Composition examples

**Live trading (single process):**
```
AlpacaAdapter → DedupMiddleware → GapFillerMiddleware → FanoutSink([
    BusPublisher(bus), TimescaleWriter(...), MetricsSink(),
])

DataClient(bus, TimescaleReader(...), LiveClock())
    → strategy.on_event(event)
```

**Backtest:**
```
ReplayAdapter(parquet) drives ReplayClock → BusPublisher(bus)
DataClient(bus, ParquetReader(parquet), replay_clock) → SAME strategy
```

**Unit test:**
```python
bus = FakeBus([tick1, tick2, bar1])
client = DataClient(bus, StaticHistory({}), FixedClock(t0))
asyncio.run(strategy.run(client))
```

## Module layout (proposed)

Two reasonable shapes — pick at scaffold time:

Flat (service-first, matches current `src/data/`):
```
src/data/
  main.py                 # server entry point (currently hello-world)
  events.py
  taxonomy.py
  clock.py
  source.py
  sink.py
  middleware.py
  bus.py
  client.py
  storage/
  adapters/
  errors.py
```

Packaged (once the Python engine is scaffolded):
```
src/sleep_trading/
  data/
    events.py
    taxonomy.py
    clock.py
    source.py
    sink.py
    middleware.py
    bus.py
    client.py
    storage/
      reader.py
      timescale.py
      parquet.py
    adapters/
      base.py
      alpaca.py
      ccxt_adapter.py
      oanda.py
      ibkr.py
      polygon.py
      replay.py
      mock.py
    errors.py
```

## Execution order

1. Event types + taxonomy (pure data, no I/O).
2. Clock + in-process `Bus`.
3. `MockSource` + `NullSink` + one test that wires them through `DataClient`.
4. Middleware (`DedupMiddleware`, `GapFillerMiddleware`) with tests.
5. First adapter: Alpaca (US equities is concrete and well-documented).
6. `TimescaleWriter` + `TimescaleReader`.
7. `ReplayAdapter` from Parquet.
8. Additional adapters: CCXT, OANDA, IBKR, Polygon — each gated on a real use case.

Ship each step with tests before the next.

## Verification (per layer, when executed)

- For each of goals 1–6, point to the abstraction that makes it true:
  - Goal 1 (swap vendor) → L4 Source + L2 SymbolMap.
  - Goal 2 (same code live/backtest) → L3 Clock + L7 DataClient.
  - Goal 3 (unit-testable) → every layer pinned by a mock in the layer below.
  - Goal 4 (parallel consumers) → L5 FanoutSink + multiple `DataClient` instances on one Bus.
  - Goal 5 (deterministic replay) → L3 ReplayClock + L4 ReplayAdapter.
  - Goal 6 (typed errors) → `errors.py` + adapters/base raising only those.
- Every abstraction has (a) a ~10-line protocol sketch, (b) at least one concrete implementation, (c) a unit-test stub.
- No vendor name, SDK type, or exception appears outside `adapters/`.

## Open questions

- In-process bus: raw `asyncio.Queue`, tiny hand-rolled fan-out, or `aiochannel`?
- Event versioning: field-addition-only discipline vs explicit `schema_version`?
- Does `BarAggregator` belong in middleware or in the feature engine above?
- Schema migration for long-running Timescale hypertables.
- Multi-source consolidation (same symbol on two venues) — upstream consolidate vs pass both through.

## Out of scope

- Vendor-specific implementations.
- Feature / strategy / execution engine abstractions.
- Service-boundary / deployment shape (NATS vs in-process vs REST) — orthogonal to this plan.
- Dashboard integration (see [`dashboard.md`](./dashboard.md)).
