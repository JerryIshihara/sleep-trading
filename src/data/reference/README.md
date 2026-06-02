# data.reference — security master

Local **security master** (reference data) for the US and Japan equity universes —
one SQLite row per listed instrument, built from public listing files.

## Sources

| Market | Source | What it gives |
| --- | --- | --- |
| US | Nasdaq Trader symbol directory (`nasdaqlisted.txt` + `otherlisted.txt`) | Full tradeable universe, ETF flag, round lot, listing venue |
| US | SEC EDGAR (`company_tickers_exchange.json`) | CIK enrichment |
| JP | JPX "List of Issues" (`data_j.xls`) | 4-digit local code, 33-sector, market segment |

## Build / refresh

```bash
cd src
.venv/bin/python -m data.reference                  # both markets, uses cached downloads
.venv/bin/python -m data.reference --market JP --refresh   # force re-download, JP only
# or, after `pip install -e .`:
build-security-master
```

Writes `_local/security_master.db` (override with `--db` or `$SLEEP_TRADING_DB`). Raw
downloads are cached under `_local/raw/`; both are git-ignored.

## Query

```python
from data.reference import connect, default_db_path

conn = connect(default_db_path())
conn.execute(
    "SELECT ticker, name, sector FROM securities "
    "WHERE market = 'JP' AND is_active = 1 AND security_type = 'common'"
).fetchall()
```

## Schema (`schema.sql`)

- **`securities`** — upsert key `(market, ticker)`. Stable cross-vendor IDs
  (`cik`/`isin`/`figi`) are nullable and backfilled by later enrichment passes.
- **`ingest_log`** — one row per ingestion run (provenance + ops history).

**Survivorship:** refreshes never delete. A ticker missing from the latest snapshot is
flipped `is_active = 0` with a `delisting_date`, so historical universes stay
reconstructable; `first_seen`/`last_seen` bound each instrument's observed lifetime.

## Caveats

- `lot_size` is the vendor's stated round lot (US values like 40/100 come straight from
  Nasdaq; JP common stocks = 100, funds left NULL).
- CIK coverage is partial (operating-company filers; ETFs/funds mostly NULL).
- `isin`/`figi` are reserved for a later OpenFIGI enrichment pass.
- No broker (moomoo) symbol crosswalk yet — that's the next layer.
