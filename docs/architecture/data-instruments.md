# Data Instruments - Architecture Spec

Status: draft
Owner: sleep-trading core
Module path: `src/data/reference/`

## 1. Purpose and scope

The data module needs one canonical way to describe market-data identities across
stocks, ETFs, indexes, and future asset classes. Today, `src/data/reference`
stores listed US/JP securities in a `securities` table, while the dashboard and
adapters carry separate hard-coded symbols for indexes, ETFs, and stocks. That
split makes it difficult to build one `SymbolMap`, one watchlist model, and one
data stream contract.

This spec defines an instrument hierarchy and reference schema for Python first.
Dashboard migration is deliberately out of scope, but the model should be able
to serve dashboard DTOs later.

Goals:

- One canonical instrument identity for anything that can produce market data.
- Asset-specific fields live in extension layers, not duplicated per table.
- Vendor symbols are aliases, never canonical identifiers.
- Adapters resolve vendor symbols through reference data and emit canonical
  symbols in `data.events`.
- Listed securities, ETFs, and non-tradable benchmark indexes can coexist in
  the same reference database.

## 2. Conceptual hierarchy

`Instrument` is the base type. Every other type extends it.

```text
Instrument
  ListedInstrument
    Equity
    Fund
  Index
```

### Instrument

Base identity for anything with market data.

Fields:

- `instrument_id`: stable internal integer primary key.
- `canonical_symbol`: stable system symbol, unique across all instruments.
- `instrument_type`: discriminator such as `stock`, `etf`, `index`.
- `name`: display name.
- `market`: broad market code such as `US`, `JP`, `HK`, `GLOBAL`.
- `currency`: quote or base currency when applicable.
- `region`: display/analysis region, such as `North America` or `Asia`.
- `country`: ISO country code when applicable.
- `is_active`: current reference-data status.
- `first_seen`, `last_seen`, `updated_at`: survivorship and audit timestamps.

Canonical examples:

- `US.AAPL`
- `US.SPY`
- `JP.7203`
- `IDX.SPX`
- `IDX.N225`

### ListedInstrument extends Instrument

Exchange-listed instruments add listing and venue metadata.

Fields:

- `ticker`: local exchange ticker, such as `AAPL` or `7203`.
- `exchange`: venue name, such as `NASDAQ` or `TSE`.
- `mic`: ISO 10383 market identifier, such as `XNAS` or `XTKS`.
- `lot_size`: round lot when known.
- `segment`: listing segment or tier.
- `listing_date`, `delisting_date`: listed lifecycle metadata.

### Equity extends ListedInstrument

Operating-company stock. This is the `stock` branch.

Fields:

- `sector`: sector classification when known.
- `industry`: industry classification when known.
- `cik`: SEC CIK for US filers.
- `isin`: ISIN when enriched.
- `figi`: FIGI when enriched.

### Fund extends ListedInstrument

Listed fund-like instruments, including ETFs, ETNs, REITs, and listed funds.
This is the `etf` branch for dashboard and watchlist purposes, with
`fund_type` preserving the more precise subtype.

Fields:

- `fund_type`: `etf`, `etn`, `reit`, `listed_fund`, or `other`.
- `issuer`: sponsor or issuer when known.
- `strategy`: broad strategy/theme when known.
- `benchmark_instrument_id`: optional reference to an `Index` instrument.

### Index extends Instrument

Benchmark or calculated index. An index is an instrument for data identity, even
when it is not directly tradable.

Fields:

- `provider`: index provider, such as `S&P Dow Jones`, `Nasdaq`, or `JPX`.
- `index_family`: family/group, such as `S&P`, `Nasdaq`, `Nikkei`, `TOPIX`.
- `calculation_region`: region represented by the index.
- `base_currency`: calculation currency when known.
- `constituent_universe`: short description of index membership.

## 3. Relational schema direction

Use one base `instruments` table plus extension tables keyed by
`instrument_id`. This keeps common identity fields centralized while allowing
stock, ETF, and index records to carry different metadata.

```sql
CREATE TABLE instruments (
    instrument_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_symbol TEXT    NOT NULL UNIQUE,
    instrument_type  TEXT    NOT NULL, -- stock | etf | index
    name             TEXT,
    market           TEXT    NOT NULL,
    currency         TEXT,
    region           TEXT,
    country          TEXT,
    is_active        INTEGER NOT NULL DEFAULT 1,
    first_seen       TEXT    NOT NULL,
    last_seen        TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL
);

CREATE TABLE listed_instruments (
    instrument_id INTEGER PRIMARY KEY REFERENCES instruments(instrument_id),
    ticker        TEXT NOT NULL,
    exchange      TEXT,
    mic           TEXT,
    lot_size      INTEGER,
    segment       TEXT,
    listing_date  TEXT,
    delisting_date TEXT,
    UNIQUE (mic, ticker)
);

CREATE TABLE equities (
    instrument_id INTEGER PRIMARY KEY REFERENCES listed_instruments(instrument_id),
    sector        TEXT,
    industry      TEXT,
    cik           TEXT,
    isin          TEXT,
    figi          TEXT
);

CREATE TABLE funds (
    instrument_id           INTEGER PRIMARY KEY REFERENCES listed_instruments(instrument_id),
    fund_type               TEXT NOT NULL,
    issuer                  TEXT,
    strategy                TEXT,
    benchmark_instrument_id INTEGER REFERENCES instruments(instrument_id)
);

CREATE TABLE indexes (
    instrument_id        INTEGER PRIMARY KEY REFERENCES instruments(instrument_id),
    provider             TEXT,
    index_family         TEXT,
    calculation_region   TEXT,
    base_currency        TEXT,
    constituent_universe TEXT
);
```

## 4. Aliases and relationships

Canonical symbols belong to the system. Vendor/source symbols belong in
`instrument_aliases`.

```sql
CREATE TABLE instrument_aliases (
    alias_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
    source        TEXT    NOT NULL,
    symbol        TEXT    NOT NULL,
    is_primary    INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT    NOT NULL,
    UNIQUE (source, symbol)
);
```

Alias source examples:

- `canonical`: `US.AAPL`, `IDX.SPX`
- `nasdaqtrader`: `AAPL`
- `jpx`: `7203`
- `alpaca`: `AAPL`
- `moomoo`: `US.AAPL`, `HK.00700`
- `yahoo`: `AAPL`, `^GSPC`, `^N225`, `000001.SS`
- `cik`, `isin`, `figi`: stable external identifiers

Relationships between instruments are separate from aliases:

```sql
CREATE TABLE instrument_relationships (
    relationship_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source_instrument_id  INTEGER NOT NULL REFERENCES instruments(instrument_id),
    target_instrument_id  INTEGER NOT NULL REFERENCES instruments(instrument_id),
    relationship_type     TEXT    NOT NULL,
    updated_at            TEXT    NOT NULL,
    UNIQUE (source_instrument_id, target_instrument_id, relationship_type)
);
```

Relationship examples:

- `tracks`: `US.SPY` tracks `IDX.SPX`
- `benchmark_for`: `IDX.TOPIX` benchmarks a JP equity universe
- `proxy_for`: `US.EWJ` can proxy broad Japan equity exposure

## 5. Python type sketch

The implementation can use dataclasses that mirror the hierarchy. The store can
still write flattened SQL rows, but source code should reason in typed records.

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Instrument:
    canonical_symbol: str
    instrument_type: str
    name: str | None
    market: str
    currency: str | None
    region: str | None
    country: str | None


@dataclass(frozen=True, slots=True)
class ListedInstrument(Instrument):
    ticker: str
    exchange: str | None
    mic: str | None
    lot_size: int | None
    segment: str | None


@dataclass(frozen=True, slots=True)
class Equity(ListedInstrument):
    sector: str | None
    industry: str | None
    cik: str | None
    isin: str | None
    figi: str | None


@dataclass(frozen=True, slots=True)
class Fund(ListedInstrument):
    fund_type: str
    issuer: str | None
    strategy: str | None
    benchmark_symbol: str | None


@dataclass(frozen=True, slots=True)
class Index(Instrument):
    provider: str | None
    index_family: str | None
    calculation_region: str | None
    base_currency: str | None
    constituent_universe: str | None


@dataclass(frozen=True, slots=True)
class InstrumentAlias:
    canonical_symbol: str
    source: str
    symbol: str
    is_primary: bool = False
```

## 6. Source normalization

Existing sources map into the hierarchy as follows:

- Nasdaq Trader rows with `ETF = N` become `Equity` unless their name indicates
  preferreds, warrants, units, rights, or ADRs. Those can remain listed
  instruments with a precise subtype until separate branches are needed.
- Nasdaq Trader rows with `ETF = Y` become `Fund` with `fund_type = etf` or
  `fund_type = etn`.
- JPX common stock rows become `Equity`.
- JPX ETF/ETN/REIT/fund rows become `Fund`.
- Curated benchmark rows become `Index`.

The existing survivorship behavior remains:

- Refreshes do not delete instruments.
- A listed instrument missing from the latest source snapshot is marked
  inactive and receives a `delisting_date`.
- Manual index rows are not delisted by US/JP listing refreshes.

## 7. Adapter symbol resolution

Adapters should not own durable symbol knowledge. At startup, each adapter builds
its `SymbolMap` from `instrument_aliases`:

1. Load all aliases for supported markets and instrument types.
2. For each instrument, map `canonical_symbol -> vendor symbol` for that adapter.
3. Subscribe to vendor symbols.
4. Normalize inbound vendor payloads back to `canonical_symbol`.
5. Emit canonical symbols in `Tick`, `Trade`, `Bar`, and `OrderbookLevel`.

Example:

```text
canonical_symbol: IDX.SPX
yahoo alias:      ^GSPC
moomoo alias:     US.SPX, if supported by OpenD

canonical_symbol: US.AAPL
alpaca alias:     AAPL
moomoo alias:     US.AAPL
```

If no alias exists for a requested source, subscription should fail with a typed
`SubscriptionError` rather than falling back to an ambiguous identity mapping.

## 8. Query helpers

The reference package should expose small helper functions around the schema:

```python
def resolve_alias(source: str, symbol: str) -> Instrument | None: ...
def aliases_for(canonical_symbol: str) -> list[InstrumentAlias]: ...
def active_instruments(
    *,
    instrument_type: str | None = None,
    market: str | None = None,
) -> list[Instrument]: ...
def symbol_map_for_source(source: str) -> dict[str, str]: ...
```

`symbol_map_for_source("moomoo")` returns canonical-to-vendor mappings for
adapter subscription. A paired reverse lookup can be built from the same alias
rows for inbound event normalization.

## 9. Migration path

This is development reference data, so the first implementation can rebuild the
local SQLite database instead of supporting an in-place production migration.

Recommended order:

1. Add the new schema tables.
2. Replace `Listing` with hierarchy-aware instrument dataclasses.
3. Update US and JP source normalization to emit `Equity` and `Fund`.
4. Add a curated index source for world benchmarks.
5. Update store upserts to write base and extension tables in one transaction.
6. Add alias generation for canonical, source, vendor, and external identifiers.
7. Update adapter symbol maps to read from `instrument_aliases`.

## 10. Open questions

- Whether `preferred`, `warrant`, `unit`, and `adr` need dedicated extension
  branches now or can stay as listed instrument subtypes.
- Whether canonical index symbols should be `IDX.SPX` globally or
  market-qualified, such as `US.IDX.SPX`.
- Whether ETF benchmark relationships should be manually curated first or
  imported from a fund metadata provider later.
- Whether alias lookup should be backed by SQLite only, or cached into an
  immutable in-memory resolver during adapter startup.
