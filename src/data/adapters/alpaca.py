"""Alpaca adapter — wraps ``alpaca-py`` (``StockDataStream``).

Emits canonical `data.events`. Requires the SDK and API keys::

    pip install "alpaca-py>=0.20"
    AdapterConfig(api_key=..., api_secret=..., feed="iex")   # "iex" free, "sip" paid

US equities only. The free plan streams the **IEX** feed (~2-3% of consolidated
volume), not the full SIP tape — fine for dev/signals, not for execution-grade
quotes. Channel mapping: ``TICKS`` -> quotes (-> `Tick`), ``TRADES`` -> trades
(-> `Trade`).

connect / subscribe / close issue real SDK calls; the websocket run-loop and
field normalizers are validated only against a live keyed feed
(integration-pending).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, Self

from data.adapters.base import (
    AdapterConfig,
    AdapterError,
    AuthError,
    Capabilities,
    Channel,
    NotConnectedError,
    SubscriptionError,
    VendorAdapter,
)
from data.events import Event, Tick, Trade

_SUPPORTED: frozenset[Channel] = frozenset({Channel.TICKS, Channel.TRADES})


def _dec(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)


def _ts(obj: Any) -> datetime:
    ts = getattr(obj, "timestamp", None)
    return ts if isinstance(ts, datetime) else datetime.now(UTC)


class AlpacaAdapter(VendorAdapter):
    """Streams Alpaca US-equity quotes/trades as canonical events."""

    name: ClassVar[str] = "alpaca"
    capabilities: ClassVar[Capabilities] = Capabilities(
        markets=("US",),
        channels=(Channel.TICKS, Channel.TRADES),
        streaming=True,
        historical=True,
    )

    def __init__(self, config: AdapterConfig | None = None) -> None:
        super().__init__(config)
        self._stream: Any = None
        self._task: asyncio.Task[None] | None = None
        self._queue: asyncio.Queue[Event] = asyncio.Queue()

    async def connect(self) -> None:
        if not (self.config.api_key and self.config.api_secret):
            raise AuthError("alpaca needs api_key + api_secret in AdapterConfig")
        try:
            from alpaca.data.live import StockDataStream  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise AdapterError("alpaca-py not installed; `pip install alpaca-py`") from exc
        try:
            self._stream = StockDataStream(
                self.config.api_key,
                self.config.api_secret,
                feed=self.config.feed or "iex",
            )
        except Exception as exc:  # vendor errors must not escape the adapter
            raise AdapterError(f"alpaca stream init failed: {exc}") from exc
        self._set_connected(True)

    async def subscribe(self, symbols: Sequence[str], channels: Sequence[Channel]) -> None:
        if self._stream is None:
            raise NotConnectedError("call connect() first")
        unsupported = [c for c in channels if c not in _SUPPORTED]
        if unsupported:
            raise SubscriptionError(f"alpaca adapter cannot stream {unsupported}")

        vendor_syms = [self.symbols.to_vendor(s) for s in symbols]
        if Channel.TICKS in channels:
            self._stream.subscribe_quotes(self._on_quote, *vendor_syms)
        if Channel.TRADES in channels:
            self._stream.subscribe_trades(self._on_trade, *vendor_syms)
        if self._task is None:
            self._task = asyncio.create_task(self._stream._run_forever())

    async def unsubscribe(self, symbols: Sequence[str], channels: Sequence[Channel]) -> None:
        if self._stream is None:
            raise NotConnectedError("call connect() first")
        vendor_syms = [self.symbols.to_vendor(s) for s in symbols]
        if Channel.TICKS in channels:
            self._stream.unsubscribe_quotes(*vendor_syms)
        if Channel.TRADES in channels:
            self._stream.unsubscribe_trades(*vendor_syms)

    async def events(self) -> AsyncIterator[Event]:
        while True:
            yield await self._queue.get()

    async def close(self) -> None:
        if self._task is not None:
            _ = self._task.cancel()
            self._task = None
        if self._stream is not None:
            try:
                await self._stream.stop_ws()
            except Exception as exc:  # best-effort, never leak a vendor error
                raise AdapterError(f"alpaca stop failed: {exc}") from exc
            finally:
                self._stream = None
        self._set_connected(False)

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def _on_quote(self, quote: Any) -> None:
        await self._queue.put(_quote_to_tick(quote, self.config.feed))

    async def _on_trade(self, trade: Any) -> None:
        await self._queue.put(_trade_to_trade(trade, self.config.feed))


def _quote_to_tick(quote: Any, feed: str | None) -> Tick:
    """Alpaca quote -> `Tick`. Attrs: ``symbol, bid_price, bid_size,
    ask_price, ask_size, timestamp``."""
    now = datetime.now(UTC)
    return Tick(
        symbol=str(getattr(quote, "symbol", "")),
        venue=(feed or "IEX").upper(),
        ts=_ts(quote),
        recv_ts=now,
        bid_price=_dec(getattr(quote, "bid_price", 0)),
        bid_size=_dec(getattr(quote, "bid_size", 0)),
        ask_price=_dec(getattr(quote, "ask_price", 0)),
        ask_size=_dec(getattr(quote, "ask_size", 0)),
    )


def _trade_to_trade(trade: Any, feed: str | None) -> Trade:
    """Alpaca trade -> `Trade`. Attrs: ``symbol, price, size, id, timestamp``."""
    now = datetime.now(UTC)
    trade_id = getattr(trade, "id", None)
    return Trade(
        symbol=str(getattr(trade, "symbol", "")),
        venue=(feed or "IEX").upper(),
        ts=_ts(trade),
        recv_ts=now,
        price=_dec(getattr(trade, "price", 0)),
        size=_dec(getattr(trade, "size", 0)),
        trade_id=str(trade_id) if trade_id is not None else None,
    )
