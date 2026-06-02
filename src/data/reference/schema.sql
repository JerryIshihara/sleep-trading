-- Security master (reference data) for the Sleep Trading data module.
--
-- One row per listed instrument per market. The natural upsert key is
-- (market, ticker); stable cross-vendor identifiers (cik/isin/figi) are
-- nullable and backfilled by later enrichment passes. Survivorship is
-- tracked via is_active + first_seen/last_seen/delisting_date: a refresh
-- that no longer sees a ticker flips it inactive instead of deleting it,
-- so historical universes stay reconstructable.

CREATE TABLE IF NOT EXISTS securities (
    security_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    market         TEXT    NOT NULL,                 -- 'US' | 'JP'
    ticker         TEXT    NOT NULL,                 -- exchange ticker (US) / local code (JP)
    name           TEXT,
    exchange       TEXT,                             -- venue: NASDAQ, NYSE, NYSE Arca, TSE, ...
    mic            TEXT,                             -- ISO 10383 MIC: XNAS, XNYS, ARCX, XTKS, ...
    security_type  TEXT    NOT NULL,                 -- common, etf, etn, reit, preferred, warrant, unit, adr, other
    currency       TEXT    NOT NULL,                 -- 'USD' | 'JPY'
    cik            TEXT,                             -- US SEC CIK (10-digit, zero-padded)
    isin           TEXT,                             -- backfilled later
    figi           TEXT,                             -- backfilled later (OpenFIGI)
    lot_size       INTEGER,                          -- round lot (US ~100; JP stocks 100; funds vary -> NULL)
    sector         TEXT,                             -- JP 33-sector name; US NULL for now
    segment        TEXT,                             -- market segment: Prime/Standard/Growth, Global Select, ...
    is_active      INTEGER NOT NULL DEFAULT 1,       -- 1 = present in latest snapshot
    listing_date   TEXT,
    delisting_date TEXT,
    source         TEXT    NOT NULL,                 -- provenance: nasdaqtrader, sec, jpx
    source_symbol  TEXT,                             -- raw symbol as the source provided it
    first_seen     TEXT    NOT NULL,                 -- ISO date first ingested
    last_seen      TEXT    NOT NULL,                 -- ISO date last present in a snapshot
    updated_at     TEXT    NOT NULL,                 -- ISO timestamp of last write
    UNIQUE (market, ticker)
);

CREATE INDEX IF NOT EXISTS idx_securities_market ON securities (market);
CREATE INDEX IF NOT EXISTS idx_securities_type   ON securities (security_type);
CREATE INDEX IF NOT EXISTS idx_securities_active ON securities (is_active);
CREATE INDEX IF NOT EXISTS idx_securities_cik    ON securities (cik);
CREATE INDEX IF NOT EXISTS idx_securities_name   ON securities (name);

-- One row per (source, market) ingestion run -- provenance + ops history.
CREATE TABLE IF NOT EXISTS ingest_log (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT    NOT NULL,
    market        TEXT    NOT NULL,
    snapshot_date TEXT    NOT NULL,
    rows_seen     INTEGER,
    rows_upserted INTEGER,
    rows_delisted INTEGER,
    status        TEXT    NOT NULL,                  -- 'ok' | 'error'
    message       TEXT,
    started_at    TEXT    NOT NULL,
    finished_at   TEXT
);
