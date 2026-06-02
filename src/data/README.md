# data

Sleep Trading data service — **hello-world skeleton**.

Proves the process shape for the real data layer (async I/O, low-latency event loop, WebSocket framing) before vendor adapters, storage, and pub/sub land. See [`../../docs/plan/data.md`](../../docs/plan/data.md) for the abstraction design this skeleton will grow into.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/healthz` | Liveness probe. Returns `ok`. |
| GET | `/hello` | `{"msg": "hello", "ts": <unix_epoch>}`. |
| GET | `/ws` | WebSocket. Emits `{"seq", "ts"}` every 50 ms. |
| GET | `/api/indices` | World-index quotes + 1D series, fetched server-side (CORS-enabled). Powers `useWorldIndices`. |
| GET | `/ws/ticks` | WebSocket. Live moomoo NASDAQ price frames `{symbol, price, prevClose, percentChange, ts}`. Powers `useNasdaqTicker`. |

## Run

Requires Python 3.11+. Install from the project root (`src/`), not this directory:

```bash
cd src
.venv/bin/python -m pip install -e .
.venv/bin/data-service        # or: .venv/bin/python -m data.main
```

Then:

```bash
curl http://127.0.0.1:8000/hello
# {"msg": "hello", "ts": 1745539200.123}

# WebSocket stream:
python -c "import asyncio, aiohttp; \
async def main():\
 async with aiohttp.ClientSession() as s, s.ws_connect('http://127.0.0.1:8000/ws') as ws:\
  for _ in range(5): print((await ws.receive()).data)\
; asyncio.run(main())"
```

## Low-latency bits

- **`uvloop`** replaces the default asyncio loop (2–4× faster on Linux / macOS). Auto-installs if available; pure stdlib fallback on Windows.
- **`access_log=None`** skips per-request logging on the hot path.
- Binds `127.0.0.1` — flip to `0.0.0.0` when it moves off the dev box.
- No middleware, no ORM, no framework overhead. Just `aiohttp` routes.

## What this is not

Not a real data service. No vendor adapters, no storage, no pub/sub, no normalization. Everything that actually handles market data lives in the plan under `../../docs/plan/data.md` and hasn't been built yet. This service exists so the deploy shape and the latency-sensitive plumbing (event loop, WS framing, JSON encoding) are proven before the larger pieces land.
