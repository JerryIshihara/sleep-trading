# Data Module — Architecture Spec

Status: draft
Owner: sleep-trading core
Module path (planned): `src/sleep_trading/data/`

## 1. Purpose & scope

The data module is the abstract layer that handles market data ingestion, normalization, storage, and replay. It is market-data-only: no orders, no fills, no account state. Inputs are vendor WebSocket streams, vendor REST endpoints, and historical files (Parquet/CSV). Outputs are normalized, typed events delivered on an in-process bus to downstream consumers (features, strategy), and persisted rows written to TimescaleDB. All vendor-specific schemas are contained behind the `DataAdapter` interface — nothing vendor-shaped leaks upward.

## 2. Core types

All event types are immutable, timezone-aware, and use `Decimal` for prices and sizes to avoid float error in accounting paths.

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Tick:
    """Top-of-book quote update (best bid / best ask)."""
    symbol: str
    venue: str
    ts: datetime                # exchange timestamp, tz-aware UTC
    recv_ts: datetime           # local receive timestamp, tz-aware UTC
    bid_price: Decimal
    bid_size: Decimal
    ask_price: Decimal
    ask_size: Decimal
    seq: int | None = None      # vendor sequence number, if provided


@dataclass(frozen=True, slots=True)
class Trade:
    """Executed print observed on the tape."""
    symbol: str
    venue: str
    ts: datetime
    recv_ts: datetime
    price: Decimal
    size: Decimal
    side: Side | None = None    # None when aggressor is unknown
    trade_id: str | None = None


@dataclass(frozen=True, slots=True)
class Bar:
    """OHLCV aggregate over a fixed interval."""
    symbol: str
    venue: str
    ts_open: datetime           # bar start, tz-aware UTC
    ts_close: datetime          # bar end, tz-aware UTC
    interval: Literal["1s", "5s", "1m", "5m", "1h", "1d"]
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trade_count: int | None = None


@dataclass(frozen=True, slots=True)
class OrderbookLevel:
    """Single level of a depth snapshot or delta."""
    symbol: str
    venue: str
    ts: datetime
    recv_ts: datetime
    side: Side
    level: int                  # 0 = top of book
    price: Decimal
    size: Decimal
    is_snapshot: bool = False   # True for full-book snapshots, False for deltas


Event = Tick | Trade | Bar | OrderbookLevel
```

Rules:
- `ts` is always the venue's timestamp. `recv_ts` is when the process observed it. Both are required.
- `symbol` uses a canonical form (e.g. `BTC-USD`, `AAPL`, `EUR_USD`). Vendor-specific forms are mapped inside the adapter.
- `venue` identifies the source exchange/ECN (`NASDAQ`, `BINANCE`, `OANDA`, `CME`). It is never the vendor name.

## 3. DataAdapter interface

Every vendor integration implements `DataAdapter`. Adapters emit only the types above — they never return vendor payloads, vendor enums, or raw dicts.

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Sequence


class Channel(str, Enum):
    TICKS = "ticks"
    TRADES = "trades"
    BARS_1M = "bars_1m"
    BARS_1S = "bars_1s"
    ORDERBOOK_L2 = "orderbook_l2"


class DataAdapter(ABC):
    """Abstract vendor adapter for market data."""

    name: str                   # e.g. "alpaca", "ccxt:binance"

    @abstractmethod
    async def connect(self) -> None:
        """Open WebSocket and authenticate. Raises ConnectionError on failure."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection. Idempotent."""

    @abstractmethod
    async def subscribe(
        self,
        symbols: Sequence[str],
        channels: Sequence[Channel],
    ) -> None:
        """Add subscriptions. Raises SubscriptionError on vendor reject."""

    @abstractmethod
    async def unsubscribe(
        self,
        symbols: Sequence[str],
        channels: Sequence[Channel],
    ) -> None:
        """Remove subscriptions. Idempotent."""

    @abstractmethod
    async def stream(self) -> AsyncIterator[Event]:
        """Yield normalized events until disconnect() or unrecoverable error."""

    @abstractmethod
    async def backfill(
        self,
        symbol: str,
        channel: Channel,
        start: datetime,
        end: datetime,
    ) -> AsyncIterator[Event]:
        """REST-based historical pull. Used on startup and after gaps."""
```

Contract:
- Adapters raise typed exceptions (`ConnectionError`, `AuthError`, `SubscriptionError`, `RateLimitError`, `DataGapError`). No swallow-and-log.
- Adapters apply backpressure by awaiting the consumer. They do not drop silently.
- Adapters MAY buffer internally during reconnect but MUST surface a `DataGapError` event or explicit gap marker if data is lost.
- `stream()` is an async generator; the consumer controls pace via `async for`.

## 4. Vendor adapters

**Alpaca** — US equities (IEX on free tier, all-exchange SIP on paid) and a basic crypto feed. Co-located with Alpaca's broker, so round-trip to execution is tight. Latency: ~10–50ms for WebSocket ticks. Coverage: NYSE/NASDAQ/ARCA equities, options, ~30 crypto pairs. Good first equities adapter because trading and data share auth and symbology.

**CCXT** — Crypto across 130+ exchanges (Binance, Kraken, Coinbase, Bybit, OKX, etc.) with a unified schema. We wrap `ccxt.pro` for WebSocket. Latency varies by exchange and region; Binance WS is ~20–80ms, smaller venues worse. Use one adapter instance per venue (`ccxt:binance`, `ccxt:kraken`) so venue-specific rate limits and reconnect logic stay isolated.

**OANDA** — FX and CFDs (38k+ pairs, metals, some indices). REST-primary with a streaming endpoint for prices; no L2 depth. Latency: ~50–150ms typical. Good for FX majors and carry/macro strategies; not for microstructure work. Broker and data share the same account, which simplifies paper/live parity for FX.

**IBKR** — Futures (ES, NQ, CL, GC), options, rates, FX, bonds, global equities. Broadest asset coverage of the set. API is TWS/Gateway via `ib_insync`; not a clean WebSocket so the adapter runs a local gateway process. Latency: ~50–200ms, variable. Use IBKR when an asset class is not covered elsewhere — it is the universal fallback, not the first choice for any single asset.

**Polygon** — US equities and options with deep historical (tick-level back ~10 years on paid tiers). Lower latency than Alpaca free tier on SIP data. Use Polygon as a second-opinion / historical source alongside Alpaca: Alpaca for live trading auth, Polygon for backfill and research datasets.

## 5. Event bus / stream

Phase 1 (single-process): `asyncio.Queue` per consumer. The adapter runs a dispatch task that `await`s on the adapter's `stream()` and `put`s to each subscribed consumer queue.

```python
class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[Event]]] = {}

    def subscribe(
        self, topic: str, maxsize: int, policy: Literal["drop_oldest", "block"]
    ) -> asyncio.Queue[Event]:
        ...

    async def publish(self, topic: str, event: Event) -> None:
        ...
```

Backpressure policy:
- **Ticks / orderbook deltas**: `drop_oldest` — high-volume, stale ticks are worthless. Drops are counted and exported as a metric.
- **Bars**: `block` — lossless; losing a bar corrupts feature state. A persistently slow bar consumer is a bug, not a drop candidate.
- **Trades**: `block` — needed for fill analysis and microstructure features.

Phase 2 (multi-process): promote to **NATS** or **Redis Streams** when a consumer (e.g. a heavy ML feature worker) needs its own process. Interface stays identical; only the bus implementation swaps. Do not build this until a concrete consumer demands it.

## 6. Storage layer

TimescaleDB (Postgres extension) for time-series persistence. One hypertable per event type, partitioned by time chunks.

Tables (sketch):

```sql
CREATE TABLE ticks (
    ts          TIMESTAMPTZ NOT NULL,
    recv_ts     TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    venue       TEXT        NOT NULL,
    bid_price   NUMERIC     NOT NULL,
    bid_size    NUMERIC     NOT NULL,
    ask_price   NUMERIC     NOT NULL,
    ask_size    NUMERIC     NOT NULL,
    seq         BIGINT,
    PRIMARY KEY (symbol, venue, ts, seq)
);
SELECT create_hypertable('ticks', 'ts', chunk_time_interval => INTERVAL '1 day');

CREATE TABLE bars (
    ts_open     TIMESTAMPTZ NOT NULL,
    ts_close    TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    venue       TEXT        NOT NULL,
    interval    TEXT        NOT NULL,
    open        NUMERIC     NOT NULL,
    high        NUMERIC     NOT NULL,
    low         NUMERIC     NOT NULL,
    close       NUMERIC     NOT NULL,
    volume      NUMERIC     NOT NULL,
    PRIMARY KEY (symbol, venue, interval, ts_open)
);
SELECT create_hypertable('bars', 'ts_open', chunk_time_interval => INTERVAL '7 days');
```

Write path:
- Batched `COPY` or `execute_values` inserts, 500–5000 rows per flush.
- Flush triggers: batch size OR 500ms timeout, whichever first.
- `ON CONFLICT DO NOTHING` for idempotency under adapter retries.

Read path separation is critical:
- **Live trading** does NOT read from Timescale. Each consumer holds an **in-memory ring buffer** sized to its required window (e.g. 2000 bars, 60s of ticks). The storage writer is a fire-and-forget sink on a separate task.
- **Research, backtest, and recovery** read from Timescale.
- Feature code is the same in both paths — a `Window` abstraction fronts either the ring buffer or a Timescale-backed iterator.

Compression and retention: continuous aggregates for 1m/5m/1h bars from raw ticks; compression policy after 7 days; retention policy per tier (ticks 90d on hot, cold archive to Parquet on S3 thereafter).

## 7. Replay for backtest

Backtest is served by `ReplayAdapter(DataAdapter)`. It reads Parquet fixtures or Timescale and yields events on the same interface.

```python
class ReplayAdapter(DataAdapter):
    def __init__(
        self,
        source: Path | str,          # Parquet file/dir or "timescale://..."
        speed: float = 0.0,          # 0 = as fast as possible; 1.0 = realtime; 10.0 = 10x
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> None: ...
```

Requirements:
- Events yielded in strict `ts` order, merged across symbols and channels.
- `recv_ts` is synthesized from `ts` plus a configurable jitter to mimic transport delay during backtest.
- Strategy code is identical between live and backtest — the swap happens at the adapter boundary only.
- No lookahead: a consumer cannot peek beyond the current `ts`. The replay source pre-sorts and streams.

## 8. Failure handling

Reconnect:
- Exponential backoff with jitter: base 1s, cap 60s, reset on 5 minutes of stable connection.
- Auth failure does not retry — surfaces `AuthError` immediately.

Gap detection:
- Sequence-based where vendor provides it (`seq`). Any skip triggers `DataGapError` with the `[last_seq, current_seq)` range.
- Timestamp-based elsewhere: per-channel expected cadence (e.g. 1m bars). Missed cadence > 2x expected triggers a gap.
- Heartbeats where the vendor offers them (Alpaca, CCXT-pro); absent heartbeat within timeout triggers a forced reconnect.

Backfill:
- On reconnect, the adapter calls `backfill()` for `[last_seen_ts, now]` on every subscribed (symbol, channel) pair.
- Backfill events flow through the same bus with a `synthetic=True`-style marker on the event metadata (TBD — see open questions) so downstream consumers can distinguish realtime from backfilled fills of a gap.

Idempotency:
- Unique key on `(symbol, venue, ts, seq)` for ticks, `(symbol, venue, interval, ts_open)` for bars.
- `ON CONFLICT DO NOTHING` at the DB layer. Consumers must also tolerate duplicate delivery (use the same keys for dedup in ring buffers during backfill merge).

## 9. Testing strategy

Layers:
- **Unit**: each adapter's normalization layer tested against a fixed set of recorded vendor payloads (golden inputs → golden `Event` outputs). No network.
- **MockAdapter**: a `DataAdapter` implementation that replays canned events from Parquet fixtures at configurable speed. Used by strategy and feature tests; swappable for the real adapter under test harnesses.
- **Golden feature tests**: given a fixed Parquet input, feature outputs must be byte-identical across runs. Catches accidental changes to normalization, bar boundaries, or timestamp handling.
- **Property tests**: monotonic `ts`, no duplicate `(symbol, venue, ts, seq)`, `Decimal` precision preserved through the pipeline.
- **Smoke tests**: nightly job connects to each vendor's sandbox (Alpaca paper, OANDA demo, CCXT testnet where available), subscribes to a known symbol, asserts at least N events in M seconds.
- **Storage tests**: Testcontainers-launched Timescale instance, round-trip insert → query → assert equality.

## 10. Open questions

- **Schema migration**: how do we version the `Event` dataclasses and their Timescale tables together? Proposal: `schema_version` column + Alembic migrations, but replay of old Parquet needs an upcast path.
- **Multi-source consolidation**: when two vendors stream the same symbol (e.g. BTC-USD from Binance and Coinbase, or AAPL from Alpaca SIP and Polygon), which wins on conflict, and do we publish both and let features pick, or consolidate upstream?
- **Redundancy across two vendors**: active-active (both streams live, primary wins, secondary fills gaps) vs active-passive (secondary warm but silent). Cost vs complexity tradeoff.
- **Corporate actions**: splits, dividends, ticker changes. Where do adjustments happen — at storage time (destructive), at read time (view/materialization), or in a separate `adjustments` table joined by the feature layer?
- **Backfill marker on events**: is a flag on the event the right shape, or should backfill flow through a separate topic so consumers opt-in?
- **Orderbook representation**: deltas-only vs periodic snapshot + deltas. Snapshot cadence and recovery strategy on partial loss.
- **Clock discipline**: do we trust `recv_ts` from a non-NTP-disciplined host? Add a per-process NTP offset field to events, or enforce chrony on all runners?
