# data.adapters — vendor adapters (L4 Source)

The boundary where external market-data APIs/resources become canonical
`data.events`. Each adapter owns **one** vendor (connection, auth, reconnect,
rate-limit, symbol mapping) and emits only `Tick` / `Trade` / `Bar` /
`OrderbookLevel`. **No vendor dict, enum, or exception escapes this layer** —
failures surface as the `AdapterError` family. This implements the L4 *Source*
contract in [`../../../docs/plan/data.md`](../../../docs/plan/data.md).

## Contract

```python
class Source(Protocol):
    async def connect(self) -> None: ...
    async def subscribe(self, symbols, channels) -> None: ...
    async def unsubscribe(self, symbols, channels) -> None: ...
    def events(self) -> AsyncIterator[Event]: ...
    async def close(self) -> None: ...
```

`Channel`: `TICKS`, `TRADES`, `BARS_1S`, `BARS_1M`, `ORDERBOOK_L2`.

## Usage

```python
from data.adapters import get_adapter, AdapterConfig, Channel

adapter = get_adapter("alpaca", AdapterConfig(api_key="…", api_secret="…", feed="iex"))
async with adapter:                                  # connect()/close()
    await adapter.subscribe(["AAPL", "MSFT"], [Channel.TICKS, Channel.TRADES])
    async for event in adapter.events():
        match event:
            case Tick():  ...
            case Trade(): ...
```

Vendor SDKs import lazily inside `connect()`, so `import data.adapters` needs
neither `moomoo-api` nor `alpaca-py`. Install per vendor:
`pip install -e '.[moomoo]'` or `.[alpaca]`.

## Adapters

| Adapter | Markets | Channels | Needs | Notes |
| --- | --- | --- | --- | --- |
| `moomoo` | US, HK, SG, CN | TICKS, TRADES | `moomoo-api` + OpenD on :11111 | ⚠️ JP stock quotes not served by OpenD yet (2026) — US/HK only |
| `alpaca` | US | TICKS, TRADES | `alpaca-py` + API keys | Free tier = **IEX** feed (~2-3% of volume), not SIP |

Introspect before wiring: `MoomooAdapter.capabilities` → `Capabilities(markets=…, channels=…)`.

## Adding an adapter

1. Subclass `VendorAdapter`; set `name` + `capabilities`.
2. Implement the five `Source` methods; lazy-import the SDK in `connect()`.
3. Translate vendor payloads to `data.events` in private normalizer funcs.
4. Raise only `AdapterError` subclasses — wrap every vendor exception.
5. Register the class in `registry.py`.

## Status

The base contract is final and type-checked (basedpyright strict). The
per-vendor **streaming bridge and field normalizers are wired but validated
only against a live feed** (OpenD / Alpaca keys) — treat them as integration-
pending. Snapshot and historical reads are a separate L8 concern, not part of
this streaming boundary.
