"""Build the security master: download listings, load SQLite, track delistings.

CLI::

    python -m data.reference [--db PATH] [--market US] [--market JP] [--refresh]

Or, after ``pip install -e .``, via the console script ``build-security-master``.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from data.reference import sources, store
from data.reference.sources import Listing

DEFAULT_DB = Path(__file__).resolve().parent / "_local" / "security_master.db"

# market -> (provenance label, fetcher)
_FETCHERS: dict[str, tuple[str, Callable[..., list[Listing]]]] = {
    "US": ("nasdaqtrader+sec", sources.fetch_us),
    "JP": ("jpx", sources.fetch_jp),
}


def default_db_path() -> Path:
    """Resolve the SQLite path (``$SLEEP_TRADING_DB`` overrides the module default)."""
    env = os.environ.get("SLEEP_TRADING_DB")
    return Path(env) if env else DEFAULT_DB


def build(
    *,
    db_path: Path | None = None,
    markets: tuple[str, ...] = ("US", "JP"),
    refresh: bool = False,
) -> dict[str, dict[str, int]]:
    """Download, normalize, and upsert listings for each market into SQLite."""
    db_path = db_path or default_db_path()
    conn = store.connect(db_path)
    store.init_db(conn)
    snapshot = date.today().isoformat()
    out: dict[str, dict[str, int]] = {}

    for market in markets:
        source_name, fetch = _FETCHERS[market]
        started = datetime.now(UTC).isoformat(timespec="seconds")
        try:
            listings = fetch(force=refresh)
            upserted = store.upsert_listings(conn, listings, snapshot)
            delisted = store.mark_delisted(conn, market, snapshot)
            conn.commit()
            store.log_run(
                conn,
                source=source_name,
                market=market,
                snapshot=snapshot,
                rows_seen=len(listings),
                rows_upserted=upserted,
                rows_delisted=delisted,
                status="ok",
                message=None,
                started_at=started,
            )
            conn.commit()
            out[market] = {"seen": len(listings), "upserted": upserted, "delisted": delisted}
        except Exception as exc:
            store.log_run(
                conn,
                source=source_name,
                market=market,
                snapshot=snapshot,
                rows_seen=0,
                rows_upserted=0,
                rows_delisted=0,
                status="error",
                message=str(exc),
                started_at=started,
            )
            conn.commit()
            raise

    conn.close()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the local security master (US + Japan listings) into SQLite."
    )
    parser.add_argument(
        "--db", type=Path, default=None, help="SQLite path (default: module _local/)."
    )
    parser.add_argument(
        "--market",
        action="append",
        choices=["US", "JP"],
        help="Limit to a market (repeatable). Default: both.",
    )
    parser.add_argument("--refresh", action="store_true", help="Force re-download (ignore cache).")
    args = parser.parse_args()

    markets = tuple(args.market) if args.market else ("US", "JP")
    db_path = args.db or default_db_path()
    results = build(db_path=db_path, markets=markets, refresh=args.refresh)

    print(f"\nSecurity master -> {db_path}")
    for market, stats in results.items():
        print(
            f"  {market}: {stats['seen']:>6} seen, {stats['upserted']:>6} upserted, "
            f"{stats['delisted']:>4} newly delisted"
        )

    conn = store.connect(db_path)
    print("\n  market   total  active  common    etf  with_cik")
    print("  " + "-" * 46)
    for r in store.summary(conn):
        print(
            f"  {r['market']:<6} {r['total']:>6} {r['active']:>7} {r['common']:>7} "
            f"{r['etf']:>6} {r['with_cik']:>9}"
        )
    conn.close()


if __name__ == "__main__":
    main()
