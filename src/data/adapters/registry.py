"""Adapter registry: resolve a vendor by name without importing its SDK.

``get_adapter("alpaca", cfg)`` returns an unconnected `Source`; the vendor SDK
is imported lazily inside ``connect()``, so importing this module never requires
``moomoo-api`` or ``alpaca-py`` to be installed. The factory typing also pins
each adapter to the `Source` contract at type-check time.
"""

from __future__ import annotations

from collections.abc import Callable

from data.adapters.alpaca import AlpacaAdapter
from data.adapters.base import AdapterConfig, AdapterError, Source
from data.adapters.moomoo import MoomooAdapter

ADAPTERS: dict[str, Callable[[AdapterConfig | None], Source]] = {
    MoomooAdapter.name: MoomooAdapter,
    AlpacaAdapter.name: AlpacaAdapter,
}


def get_adapter(name: str, config: AdapterConfig | None = None) -> Source:
    """Instantiate a registered adapter by name (e.g. ``"moomoo"``, ``"alpaca"``)."""
    try:
        factory = ADAPTERS[name]
    except KeyError:
        known = ", ".join(sorted(ADAPTERS))
        raise AdapterError(f"unknown adapter {name!r}; known: {known}") from None
    return factory(config)


def available() -> list[str]:
    """Names of all registered adapters."""
    return sorted(ADAPTERS)
