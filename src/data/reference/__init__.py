"""Security master -- reference data (listings) for US and Japan.

Build or refresh the local SQLite security master::

    from data.reference import build
    build()                        # downloads US + JP, upserts _local/security_master.db

Then query it with the standard library::

    from data.reference import connect, default_db_path
    conn = connect(default_db_path())
    rows = conn.execute(
        "SELECT ticker, name FROM securities WHERE market = 'JP' AND is_active = 1"
    ).fetchall()

Sources: Nasdaq Trader symbol directory + SEC EDGAR (US), JPX List of Issues (JP).
See ``docs/plan/data.md`` for where this fits the data layer.
"""

from __future__ import annotations

from data.reference.build import build, default_db_path
from data.reference.sources import Listing, fetch_jp, fetch_us
from data.reference.store import connect, init_db, summary

__all__ = [
    "Listing",
    "build",
    "connect",
    "default_db_path",
    "fetch_jp",
    "fetch_us",
    "init_db",
    "summary",
]
