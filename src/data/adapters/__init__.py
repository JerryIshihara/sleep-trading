"""Vendor adapters — the L4 *Source* boundary of the data layer.

Each adapter wraps one external API/resource (moomoo, Alpaca, …) and emits
**only** canonical `data.events`; no vendor type or exception escapes here. See
``docs/plan/data.md`` for the full eight-layer design.

    from data.adapters import get_adapter, AdapterConfig, Channel

    adapter = get_adapter("alpaca", AdapterConfig(api_key=..., api_secret=...))
    async with adapter:
        await adapter.subscribe(["AAPL"], [Channel.TICKS, Channel.TRADES])
        async for event in adapter.events():
            ...

Vendor SDKs are imported lazily inside ``connect()``, so importing this package
needs neither ``moomoo-api`` nor ``alpaca-py`` installed.
"""

from __future__ import annotations

from data.adapters.alpaca import AlpacaAdapter
from data.adapters.base import (
    AdapterConfig,
    AdapterError,
    AuthError,
    Capabilities,
    Channel,
    NotConnectedError,
    Source,
    SubscriptionError,
    SymbolMap,
    VendorAdapter,
)
from data.adapters.moomoo import MoomooAdapter
from data.adapters.registry import ADAPTERS, available, get_adapter

__all__ = [
    "ADAPTERS",
    "AdapterConfig",
    "AdapterError",
    "AlpacaAdapter",
    "AuthError",
    "Capabilities",
    "Channel",
    "MoomooAdapter",
    "NotConnectedError",
    "Source",
    "SubscriptionError",
    "SymbolMap",
    "VendorAdapter",
    "available",
    "get_adapter",
]
