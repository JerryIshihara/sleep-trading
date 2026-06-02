"""Adapter contract: vendor APIs in, canonical ``data.events`` out.

This is the **L4 Source** boundary from ``docs/plan/data.md``. A vendor adapter
owns exactly one vendor's connection (auth, reconnect, rate-limit, symbol
mapping) and emits **only** `data.events` types. No vendor dict, enum, or
exception is allowed to escape this layer -- failures surface as the
`AdapterError` family below (design goal 6: typed errors at every seam).

`Source` is a structural `Protocol` (per the plan, the layer is built on
Protocols, not inheritance). `VendorAdapter` is an optional shared-state base;
concrete adapters subclass it for the common plumbing and implement the `Source`
methods. `Channel` / `SymbolMap` live here for now and migrate up to a dedicated
``data.taxonomy`` (L2) module when that layer is scaffolded.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar, Protocol, runtime_checkable

from data.events import Event


class Channel(StrEnum):
    """Subscribable data streams, canonical and vendor-agnostic."""

    TICKS = "ticks"  # top-of-book bid/ask -> Tick
    TRADES = "trades"  # executed prints -> Trade
    BARS_1S = "bars_1s"  # 1-second OHLCV -> Bar
    BARS_1M = "bars_1m"  # 1-minute OHLCV -> Bar
    ORDERBOOK_L2 = "orderbook_l2"  # depth -> OrderbookLevel


# ── Typed errors — no vendor exception escapes the adapter (goal 6) ──────────
class AdapterError(Exception):
    """Base for every error surfaced by an adapter."""


class NotConnectedError(AdapterError):
    """Operation requires an open connection; call ``connect()`` first."""


class SubscriptionError(AdapterError):
    """A subscribe / unsubscribe request was rejected by the vendor."""


class AuthError(AdapterError):
    """Credentials are missing or were rejected by the vendor."""


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What an adapter actually supports — introspect before wiring it."""

    markets: tuple[str, ...] = ()  # e.g. ("US", "HK")
    channels: tuple[Channel, ...] = ()
    streaming: bool = False
    historical: bool = False


@dataclass(frozen=True, slots=True)
class AdapterConfig:
    """Connection + auth knobs. Each adapter uses the subset it needs."""

    host: str = "127.0.0.1"
    port: int = 11111
    api_key: str | None = None
    api_secret: str | None = None
    paper: bool = True
    feed: str | None = None  # e.g. alpaca "iex" (free) | "sip" (paid)


@dataclass(slots=True)
class SymbolMap:
    """Canonical <-> vendor symbol mapping, owned by the adapter (L2)."""

    _to_vendor: dict[str, str] = field(default_factory=dict)
    _to_canonical: dict[str, str] = field(default_factory=dict)

    def add(self, canonical: str, vendor: str) -> None:
        self._to_vendor[canonical] = vendor
        self._to_canonical[vendor] = canonical

    def to_vendor(self, canonical: str) -> str:
        return self._to_vendor.get(canonical, canonical)

    def to_canonical(self, vendor: str) -> str:
        return self._to_canonical.get(vendor, vendor)


@runtime_checkable
class Source(Protocol):
    """The only shape the rest of the system depends on (L4)."""

    async def connect(self) -> None: ...
    async def subscribe(self, symbols: Sequence[str], channels: Sequence[Channel]) -> None: ...
    async def unsubscribe(self, symbols: Sequence[str], channels: Sequence[Channel]) -> None: ...
    def events(self) -> AsyncIterator[Event]: ...
    async def close(self) -> None: ...


class VendorAdapter:
    """Shared plumbing for one-vendor adapters.

    Subclasses set ``name`` / ``capabilities`` and implement the `Source`
    methods (``connect``, ``subscribe``, ``unsubscribe``, ``events``, ``close``)
    plus the async-context-manager sugar, emitting only `data.events`. This base
    holds the common state (config, symbol map, connection flag) and is *not*
    abstract — conformance to `Source` is enforced structurally at the registry.
    """

    name: ClassVar[str]
    capabilities: ClassVar[Capabilities]

    def __init__(self, config: AdapterConfig | None = None) -> None:
        self.config: AdapterConfig = config or AdapterConfig()
        self.symbols: SymbolMap = SymbolMap()
        self._connected: bool = False

    @property
    def connected(self) -> bool:
        return self._connected

    def _set_connected(self, value: bool) -> None:
        self._connected = value


__all__ = [
    "AdapterConfig",
    "AdapterError",
    "AuthError",
    "Capabilities",
    "Channel",
    "NotConnectedError",
    "Source",
    "SubscriptionError",
    "SymbolMap",
    "VendorAdapter",
]
