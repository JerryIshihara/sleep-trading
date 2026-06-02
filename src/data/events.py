"""Canonical market-data event types.

Frozen, immutable dataclasses with strict typing. Every event carries the
venue timestamp (`ts`) and the local receive timestamp (`recv_ts`), both
tz-aware UTC. Prices and sizes use `Decimal` so accounting math never
inherits float error.

See docs/architecture/data-module.md §2 for the full spec.

Rules:
- `ts` is the venue's timestamp; `recv_ts` is when this process observed it.
- `symbol` is canonical per asset class (e.g. "AAPL", "BTC-USD", "EUR_USD").
- `venue` is the exchange/ECN code (e.g. "NASDAQ", "BINANCE"), never the vendor.

These types are pure data — no I/O, no logging, no vendor coupling. Vendor
adapters live elsewhere and emit these as their only public output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


BarInterval = Literal["1s", "5s", "1m", "5m", "1h", "1d"]


@dataclass(frozen=True, slots=True)
class Tick:
    """Top-of-book quote update (best bid / best ask)."""

    symbol: str
    venue: str
    ts: datetime
    recv_ts: datetime
    bid_price: Decimal
    bid_size: Decimal
    ask_price: Decimal
    ask_size: Decimal
    seq: int | None = None


@dataclass(frozen=True, slots=True)
class Trade:
    """Executed print observed on the tape."""

    symbol: str
    venue: str
    ts: datetime
    recv_ts: datetime
    price: Decimal
    size: Decimal
    side: Side | None = None
    trade_id: str | None = None


@dataclass(frozen=True, slots=True)
class Bar:
    """OHLCV aggregate over a fixed interval."""

    symbol: str
    venue: str
    ts_open: datetime
    ts_close: datetime
    interval: BarInterval
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
    level: int
    price: Decimal
    size: Decimal
    is_snapshot: bool = False


Event = Tick | Trade | Bar | OrderbookLevel


__all__ = [
    "Bar",
    "BarInterval",
    "Event",
    "OrderbookLevel",
    "Side",
    "Tick",
    "Trade",
]
