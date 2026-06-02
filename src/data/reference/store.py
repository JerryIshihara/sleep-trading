"""SQLite persistence for the security master.

Thin wrapper over the standard-library ``sqlite3``: open a connection, apply
the schema, upsert `Listing` rows keyed on (market, ticker), and flip any
ticker missing from the latest snapshot to inactive (survivorship tracking).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from data.reference.sources import Listing

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

_UPSERT = """
INSERT INTO securities (
    market, ticker, name, exchange, mic, security_type, currency,
    cik, isin, figi, lot_size, sector, segment,
    is_active, source, source_symbol, first_seen, last_seen, updated_at
) VALUES (
    :market, :ticker, :name, :exchange, :mic, :security_type, :currency,
    :cik, :isin, NULL, :lot_size, :sector, :segment,
    1, :source, :source_symbol, :snapshot, :snapshot, :now
)
ON CONFLICT(market, ticker) DO UPDATE SET
    name           = excluded.name,
    exchange       = excluded.exchange,
    mic            = excluded.mic,
    security_type  = excluded.security_type,
    currency       = excluded.currency,
    cik            = COALESCE(excluded.cik, securities.cik),
    lot_size       = excluded.lot_size,
    sector         = excluded.sector,
    segment        = excluded.segment,
    is_active      = 1,
    delisting_date = NULL,
    source         = excluded.source,
    source_symbol  = excluded.source_symbol,
    last_seen      = excluded.last_seen,
    updated_at     = excluded.updated_at
"""

_MARK_DELISTED = """
UPDATE securities
   SET is_active = 0,
       delisting_date = COALESCE(delisting_date, :snapshot),
       updated_at = :now
 WHERE market = :market AND is_active = 1 AND last_seen < :snapshot
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (creating parent dirs as needed) a WAL-mode SQLite connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Apply the schema (idempotent)."""
    conn.executescript(_SCHEMA_PATH.read_text())
    conn.commit()


def upsert_listings(conn: sqlite3.Connection, listings: Iterable[Listing], snapshot: str) -> int:
    """Insert or refresh listings for the given snapshot date. Returns row count."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    params = [
        {
            "market": x.market,
            "ticker": x.ticker,
            "name": x.name,
            "exchange": x.exchange,
            "mic": x.mic,
            "security_type": x.security_type,
            "currency": x.currency,
            "cik": x.cik,
            "isin": x.isin,
            "lot_size": x.lot_size,
            "sector": x.sector,
            "segment": x.segment,
            "source": x.source,
            "source_symbol": x.source_symbol,
            "snapshot": snapshot,
            "now": now,
        }
        for x in listings
    ]
    conn.executemany(_UPSERT, params)
    return len(params)


def mark_delisted(conn: sqlite3.Connection, market: str, snapshot: str) -> int:
    """Flag tickers absent from this snapshot as inactive. Returns rows changed."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    cur = conn.execute(_MARK_DELISTED, {"market": market, "snapshot": snapshot, "now": now})
    return cur.rowcount


def log_run(
    conn: sqlite3.Connection,
    *,
    source: str,
    market: str,
    snapshot: str,
    rows_seen: int,
    rows_upserted: int,
    rows_delisted: int,
    status: str,
    message: str | None,
    started_at: str,
) -> None:
    """Record one ingestion run in ``ingest_log``."""
    conn.execute(
        """
        INSERT INTO ingest_log (
            source, market, snapshot_date, rows_seen, rows_upserted,
            rows_delisted, status, message, started_at, finished_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source,
            market,
            snapshot,
            rows_seen,
            rows_upserted,
            rows_delisted,
            status,
            message,
            started_at,
            datetime.now(UTC).isoformat(timespec="seconds"),
        ),
    )


def summary(conn: sqlite3.Connection) -> Sequence[sqlite3.Row]:
    """Per-market counts for a quick post-build sanity check."""
    return conn.execute(
        """
        SELECT market,
               COUNT(*)                                                    AS total,
               SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END)              AS active,
               SUM(CASE WHEN security_type = 'common' THEN 1 ELSE 0 END)   AS common,
               SUM(CASE WHEN security_type IN ('etf', 'etn') THEN 1 ELSE 0 END) AS etf,
               SUM(CASE WHEN cik IS NOT NULL THEN 1 ELSE 0 END)            AS with_cik
          FROM securities
         GROUP BY market
         ORDER BY market
        """
    ).fetchall()
