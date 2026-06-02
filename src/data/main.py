"""Sleep Trading — data service (hello-world skeleton).

Placeholder entry point. Proves the process shape for a low-latency async
server with a WebSocket tick stream. Does not yet connect to any vendor or
storage. See docs/plan/data.md for the abstraction design this will grow
into.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, TypedDict

from aiohttp import ClientError, ClientSession, ClientTimeout, web

try:
    import uvloop  # type: ignore[import-not-found]

    uvloop.install()
except ImportError:
    pass


HOST = "127.0.0.1"
PORT = 8000
TICK_INTERVAL_S = 0.05  # 20 Hz


async def health(_: web.Request) -> web.Response:
    return web.Response(text="ok")


async def hello(_: web.Request) -> web.Response:
    return web.json_response({"msg": "hello", "ts": time.time()})


async def ws_stream(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=30.0)
    await ws.prepare(request)
    n = 0
    try:
        while not ws.closed:
            await ws.send_json({"seq": n, "ts": time.time()})
            n += 1
            await asyncio.sleep(TICK_INTERVAL_S)
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    return ws


# ── World index proxy ────────────────────────────────────────────────────────
# Fetch index quote + intraday series server-side (no browser CORS) and serve the
# shape the dashboard's useWorldIndices hook consumes. Cached briefly so polling
# does not hammer the upstream. This is where moomoo (HK/US) can later override
# specific symbols; the rest stay on the proxied public feed.

INDEX_SYMBOLS: dict[str, str] = {
    "SPX": "^GSPC",
    "IXIC": "^IXIC",
    "DJI": "^DJI",
    "RUT": "^RUT",
    "GSPTSE": "^GSPTSE",
    "IBOV": "^BVSP",
    "UKX": "^FTSE",
    "DAX": "^GDAXI",
    "FCHI": "^FCHI",
    "SXXP": "^STOXX",
    "N225": "^N225",
    "TOPIX": "^TOPX",
    "HSI": "^HSI",
    "SHCOMP": "000001.SS",
    "KS11": "^KS11",
    "XJO": "^AXJO",
}

_INDEX_TTL_S = 30.0
_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=15m&range=1d"
_YAHOO_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) sleep-trading/0.1"


class IndexQuote(TypedDict):
    symbol: str
    last: float
    change: float
    percentChange: float
    series: list[float]


_index_cache: list[IndexQuote] = []
_index_cache_at = 0.0


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


async def _fetch_index(session: ClientSession, symbol: str, yahoo: str) -> IndexQuote | None:
    """Fetch one index from the public chart feed. Returns None on any failure."""
    try:
        async with session.get(
            _YAHOO_CHART.format(symbol=yahoo),
            headers={"User-Agent": _YAHOO_UA},
            timeout=ClientTimeout(total=6),
        ) as resp:
            if resp.status != 200:
                return None
            body = await resp.json()
        result = body["chart"]["result"][0]
        meta = result["meta"]
        closes = result["indicators"]["quote"][0]["close"]
        series = [float(c) for c in closes if isinstance(c, (int, float))]
        prev = _as_float(meta.get("chartPreviousClose")) or _as_float(meta.get("previousClose"))
        last = _as_float(meta.get("regularMarketPrice")) or (series[-1] if series else None)
        if last is None or prev is None or prev == 0:
            return None
        change = last - prev
        return IndexQuote(
            symbol=symbol,
            last=last,
            change=change,
            percentChange=change / prev * 100,
            series=series,
        )
    except (TimeoutError, ClientError, KeyError, IndexError, ValueError):
        return None


async def _load_indices() -> list[IndexQuote]:
    async with ClientSession() as session:
        tasks = [_fetch_index(session, sym, yahoo) for sym, yahoo in INDEX_SYMBOLS.items()]
        results = await asyncio.gather(*tasks)
    return [quote for quote in results if quote is not None]


async def indices(_: web.Request) -> web.Response:
    global _index_cache, _index_cache_at
    now = time.monotonic()
    if not _index_cache or now - _index_cache_at >= _INDEX_TTL_S:
        fresh = await _load_indices()
        if fresh:
            _index_cache = fresh
            _index_cache_at = now
    return web.json_response(_index_cache, headers={"Access-Control-Allow-Origin": "*"})


# ── NASDAQ tick stream (moomoo OpenD) ────────────────────────────────────────
# Polls moomoo snapshots for a basket of Nasdaq names and fans price frames out
# to every /ws/ticks client, in the shape the dashboard's useNasdaqTicker hook
# consumes — flipping that ticker from "Simulated" to "Live". Snapshot polling is
# the robust path (works whenever OpenD is up); the lower-latency tick-by-tick
# variant is data.adapters.MoomooAdapter (Channel.TRADES) over the same feed.
# Degrades silently when OpenD is unreachable (the ticker stays simulated).

NASDAQ_TICK_SYMBOLS = [
    "US.AAPL",
    "US.NVDA",
    "US.MSFT",
    "US.AMZN",
    "US.META",
    "US.GOOGL",
    "US.AVGO",
    "US.TSLA",
    "US.QQQ",
]
_TICK_POLL_S = 1.5

_tick_clients: set[web.WebSocketResponse] = set()
_tick_pump: asyncio.Task[None] | None = None
_quote_ctx: Any = None


def _open_quote_ctx() -> Any:
    """Create a moomoo OpenQuoteContext (sync). Returns None if unavailable."""
    try:
        from moomoo import OpenQuoteContext
    except ImportError:
        return None
    try:
        return OpenQuoteContext(host="127.0.0.1", port=11111)
    except Exception:
        return None


def _snapshot_frames(ctx: Any, symbols: list[str]) -> list[dict[str, object]]:
    """Poll moomoo snapshots (sync) -> tick frames. Returns [] on failure."""
    from moomoo import RET_OK

    try:
        ret, data = ctx.get_market_snapshot(symbols)
    except Exception:
        return []
    if ret != RET_OK:
        return []
    now = time.time() * 1000.0
    frames: list[dict[str, object]] = []
    for record in data.to_dict("records"):
        last = _as_float(record.get("last_price"))
        if last is None:
            continue
        prev = _as_float(record.get("prev_close_price")) or last
        frames.append(
            {
                "symbol": str(record.get("code", "")).rsplit(".", 1)[-1],
                "price": last,
                "prevClose": prev,
                "percentChange": (last - prev) / prev * 100 if prev else 0.0,
                "ts": now,
            }
        )
    return frames


async def _run_tick_pump() -> None:
    """Poll moomoo and fan out frames to all /ws/ticks clients."""
    global _quote_ctx
    loop = asyncio.get_running_loop()
    if _quote_ctx is None:
        _quote_ctx = await loop.run_in_executor(None, _open_quote_ctx)
    while _tick_clients and _quote_ctx is not None:
        frames = await loop.run_in_executor(None, _snapshot_frames, _quote_ctx, NASDAQ_TICK_SYMBOLS)
        if frames:
            for client in list(_tick_clients):
                if client.closed:
                    _tick_clients.discard(client)
                    continue
                try:
                    await client.send_json(frames)
                except (ConnectionResetError, RuntimeError):
                    _tick_clients.discard(client)
        await asyncio.sleep(_TICK_POLL_S)


async def ws_ticks(request: web.Request) -> web.WebSocketResponse:
    global _tick_pump
    ws = web.WebSocketResponse(heartbeat=30.0)
    await ws.prepare(request)
    _tick_clients.add(ws)
    if _tick_pump is None or _tick_pump.done():
        _tick_pump = asyncio.create_task(_run_tick_pump())
    try:
        async for _ in ws:
            pass
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        _tick_clients.discard(ws)
    return ws


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/healthz", health)
    app.router.add_get("/hello", hello)
    app.router.add_get("/ws", ws_stream)
    app.router.add_get("/api/indices", indices)
    app.router.add_get("/ws/ticks", ws_ticks)
    return app


def main() -> None:
    web.run_app(
        build_app(),
        host=HOST,
        port=PORT,
        access_log=None,
    )


if __name__ == "__main__":
    main()
