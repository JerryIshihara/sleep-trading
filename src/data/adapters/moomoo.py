"""moomoo OpenD adapter — wraps ``moomoo-api`` (``OpenQuoteContext``).

Emits canonical `data.events`. Requires the SDK plus a running OpenD gateway::

    pip install "moomoo-api>=10.4"      # and OpenD on 127.0.0.1:11111

Channel mapping: ``TICKS`` -> ``ORDER_BOOK`` (level-1 -> `Tick`),
``TRADES`` -> ``TICKER`` (-> `Trade`).

⚠️ As of 2026 OpenD does **not** serve JP (``JP.xxxx``) stock quotes — only
US / HK / SG / CN. FUTUJP *account* queries work, but JP market data fails
server-side until JP launch; use ``data.reference`` for the JP universe.

The connect / subscribe / close calls are concrete SDK calls; the push->queue
bridge and field normalizers encode moomoo's documented schema but are
validated only against a live OpenD feed (integration-pending).
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
    Capabilities,
    Channel,
    NotConnectedError,
    SubscriptionError,
    VendorAdapter,
)
from data.events import Event, Tick, Trade

# canonical Channel -> moomoo SubType attribute name (resolved lazily on the SDK)
_CHANNEL_SUBTYPE: dict[Channel, str] = {
    Channel.TICKS: "ORDER_BOOK",
    Channel.TRADES: "TICKER",
}


def _dec(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)


def _venue(code: str) -> str:
    """`US.AAPL` -> `US`. Placeholder until ref-data supplies the real MIC."""
    return code.split(".", 1)[0] if "." in code else code


class MoomooAdapter(VendorAdapter):
    """Streams moomoo OpenD quotes as canonical events."""

    name: ClassVar[str] = "moomoo"
    capabilities: ClassVar[Capabilities] = Capabilities(
        markets=("US", "HK", "SG", "CN"),
        channels=(Channel.TICKS, Channel.TRADES),
        streaming=True,
        historical=True,
    )

    def __init__(self, config: AdapterConfig | None = None) -> None:
        super().__init__(config)
        self._ctx: Any = None
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self) -> None:
        try:
            from moomoo import OpenQuoteContext
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise AdapterError("moomoo-api not installed; `pip install moomoo-api`") from exc
        self._ctx = OpenQuoteContext(host=self.config.host, port=self.config.port)
        self._loop = asyncio.get_running_loop()
        self._set_connected(True)

    async def subscribe(self, symbols: Sequence[str], channels: Sequence[Channel]) -> None:
        if self._ctx is None:
            raise NotConnectedError("call connect() first")
        from moomoo import RET_OK, SubType

        unsupported = [c for c in channels if c not in _CHANNEL_SUBTYPE]
        if unsupported:
            raise SubscriptionError(f"moomoo adapter cannot stream {unsupported}")

        sub_types = [getattr(SubType, _CHANNEL_SUBTYPE[c]) for c in channels]
        vendor_syms = [self.symbols.to_vendor(s) for s in symbols]
        self._install_handlers(channels)
        ret, err = self._ctx.subscribe(vendor_syms, sub_types, subscribe_push=True)
        if ret != RET_OK:
            raise SubscriptionError(str(err))

    async def unsubscribe(self, symbols: Sequence[str], channels: Sequence[Channel]) -> None:
        if self._ctx is None:
            raise NotConnectedError("call connect() first")
        from moomoo import RET_OK, SubType

        sub_types = [
            getattr(SubType, _CHANNEL_SUBTYPE[c]) for c in channels if c in _CHANNEL_SUBTYPE
        ]
        vendor_syms = [self.symbols.to_vendor(s) for s in symbols]
        ret, err = self._ctx.unsubscribe(vendor_syms, sub_types)
        if ret != RET_OK:
            raise SubscriptionError(str(err))

    async def events(self) -> AsyncIterator[Event]:
        while True:
            yield await self._queue.get()

    async def close(self) -> None:
        if self._ctx is not None:
            self._ctx.close()
            self._ctx = None
        self._set_connected(False)

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    # ── push → queue bridge (integration-pending) ───────────────────────────
    def _emit(self, event: Event) -> None:
        """Thread-safe hand-off from an SDK handler thread to the asyncio queue."""
        if self._loop is not None:
            _ = self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    def _install_handlers(self, channels: Sequence[Channel]) -> None:
        """Register normalizing SDK handlers for the requested channels."""
        from moomoo import OrderBookHandlerBase, TickerHandlerBase

        adapter = self

        if Channel.TICKS in channels:

            class _BookHandler(OrderBookHandlerBase):  # pyright: ignore[reportUntypedBaseClass]
                def on_recv_rsp(self, rsp_pb: object) -> tuple[int, Any]:
                    ret, data = super().on_recv_rsp(rsp_pb)
                    if ret == 0:
                        adapter._emit(_orderbook_to_tick(data))
                    return ret, data

            self._ctx.set_handler(_BookHandler())

        if Channel.TRADES in channels:

            class _TickerHandler(TickerHandlerBase):  # pyright: ignore[reportUntypedBaseClass]
                def on_recv_rsp(self, rsp_pb: object) -> tuple[int, Any]:
                    ret, data = super().on_recv_rsp(rsp_pb)
                    if ret == 0:
                        for trade in _ticker_frame_to_trades(data):
                            adapter._emit(trade)
                    return ret, data

            self._ctx.set_handler(_TickerHandler())


def _orderbook_to_tick(data: Any) -> Tick:
    """moomoo order-book payload -> level-1 `Tick`. Schema: dict with
    ``code`` and ``Bid``/``Ask`` lists of ``(price, volume, ...)`` tuples."""
    code = str(data.get("code", ""))
    bid = data.get("Bid") or [(0, 0)]
    ask = data.get("Ask") or [(0, 0)]
    now = datetime.now(UTC)
    return Tick(
        symbol=code,
        venue=_venue(code),
        ts=now,
        recv_ts=now,
        bid_price=_dec(bid[0][0]),
        bid_size=_dec(bid[0][1]),
        ask_price=_dec(ask[0][0]),
        ask_size=_dec(ask[0][1]),
    )


def _ticker_frame_to_trades(data: Any) -> list[Trade]:
    """moomoo TICKER DataFrame -> `Trade` list. Columns: ``code, time, price,
    volume, sequence`` per the OpenAPI tick-by-tick schema."""
    now = datetime.now(UTC)
    trades: list[Trade] = []
    for row in data.to_dict("records"):
        code = str(row.get("code", ""))
        trades.append(
            Trade(
                symbol=code,
                venue=_venue(code),
                ts=now,
                recv_ts=now,
                price=_dec(row.get("price")),
                size=_dec(row.get("volume")),
                trade_id=str(row.get("sequence")) if row.get("sequence") is not None else None,
            )
        )
    return trades
