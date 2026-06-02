"""Listing sources for the security master.

Downloads and normalizes public listing files into `Listing` records:

- US: Nasdaq Trader symbol directory (`nasdaqlisted.txt` + `otherlisted.txt`)
  for the tradeable universe, enriched with SEC EDGAR CIK numbers.
- JP: Japan Exchange Group (JPX) "List of Issues" (`data_j.xls`).

Each source returns vendor-neutral `Listing` rows; all temporal bookkeeping
(first_seen / last_seen / delisting) is the store's job, not the source's.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

# Public listing endpoints. SEC requires a descriptive User-Agent.
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
JPX_LISTED_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
)

_UA = "sleep-trading security-master (j.ishihara1997@gmail.com)"
_CACHE_DIR = Path(__file__).resolve().parent / "_local" / "raw"

# otherlisted.txt single-letter Exchange code -> (venue, ISO 10383 MIC).
_US_EXCHANGE: dict[str, tuple[str, str]] = {
    "A": ("NYSE American", "XASE"),
    "N": ("NYSE", "XNYS"),
    "P": ("NYSE Arca", "ARCX"),
    "Z": ("Cboe BZX", "BATS"),
    "V": ("IEX", "IEXG"),
    "M": ("NYSE Chicago", "XCHI"),
}

# nasdaqlisted.txt Market Category -> human-readable tier.
_NASDAQ_TIER: dict[str, str] = {
    "Q": "Global Select",
    "G": "Global Market",
    "S": "Capital Market",
}


@dataclass(frozen=True, slots=True)
class Listing:
    """One normalized listing row, vendor-neutral."""

    market: str
    ticker: str
    name: str | None
    exchange: str | None
    mic: str | None
    security_type: str
    currency: str
    cik: str | None
    isin: str | None
    lot_size: int | None
    sector: str | None
    segment: str | None
    source: str
    source_symbol: str


def _download(url: str, dest: Path, *, force: bool = False) -> Path:
    """Fetch `url` to `dest`, returning the cached path. No-op if already cached."""
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, headers={"User-Agent": _UA}, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def _norm_key(ticker: str) -> str:
    """Normalize a ticker for cross-source joins (drop class separators)."""
    return ticker.upper().replace(".", "").replace("-", "")


def _us_type(name: str, *, is_etf: bool) -> str:
    n = name.lower()
    if is_etf:
        return "etn" if "etn" in n else "etf"
    if "preferred" in n or " pfd" in n or "pref " in n:
        return "preferred"
    if "warrant" in n:
        return "warrant"
    if "unit" in n:
        return "unit"
    if "right" in n:
        return "right"
    if "depositary" in n:
        return "adr"
    return "common"


def _parse_int(value: str | None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _load_sec_cik(path: Path) -> dict[str, str]:
    """ticker (separators stripped, upper) -> zero-padded 10-digit CIK."""
    payload = json.loads(path.read_text())
    fields: list[str] = payload["fields"]
    i_cik, i_tkr = fields.index("cik"), fields.index("ticker")
    out: dict[str, str] = {}
    for row in payload["data"]:
        out[_norm_key(str(row[i_tkr]))] = f"{int(row[i_cik]):010d}"
    return out


def fetch_us(*, force: bool = False) -> list[Listing]:
    """US tradeable universe (Nasdaq + NYSE family), CIK-enriched from SEC."""
    nasdaq = _download(NASDAQ_LISTED_URL, _CACHE_DIR / "nasdaqlisted.txt", force=force)
    other = _download(OTHER_LISTED_URL, _CACHE_DIR / "otherlisted.txt", force=force)
    sec = _download(SEC_TICKERS_URL, _CACHE_DIR / "company_tickers_exchange.json", force=force)
    cik_by_ticker = _load_sec_cik(sec)

    listings: list[Listing] = []

    with nasdaq.open(encoding="latin-1", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="|"):
            sym = (row.get("Symbol") or "").strip()
            if not sym or sym.startswith("File Creation Time") or row.get("Test Issue") == "Y":
                continue
            name = (row.get("Security Name") or "").strip() or None
            listings.append(
                Listing(
                    market="US",
                    ticker=sym,
                    name=name,
                    exchange="NASDAQ",
                    mic="XNAS",
                    security_type=_us_type(name or "", is_etf=row.get("ETF") == "Y"),
                    currency="USD",
                    cik=cik_by_ticker.get(_norm_key(sym)),
                    isin=None,
                    lot_size=_parse_int(row.get("Round Lot Size")),
                    sector=None,
                    segment=_NASDAQ_TIER.get((row.get("Market Category") or "").strip()),
                    source="nasdaqtrader",
                    source_symbol=sym,
                )
            )

    with other.open(encoding="latin-1", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="|"):
            sym = (row.get("ACT Symbol") or "").strip()
            if not sym or sym.startswith("File Creation Time") or row.get("Test Issue") == "Y":
                continue
            name = (row.get("Security Name") or "").strip() or None
            venue, mic = _US_EXCHANGE.get((row.get("Exchange") or "").strip(), (None, None))
            listings.append(
                Listing(
                    market="US",
                    ticker=sym,
                    name=name,
                    exchange=venue,
                    mic=mic,
                    security_type=_us_type(name or "", is_etf=row.get("ETF") == "Y"),
                    currency="USD",
                    cik=cik_by_ticker.get(_norm_key(sym)),
                    isin=None,
                    lot_size=_parse_int(row.get("Round Lot Size")),
                    sector=None,
                    segment=None,
                    source="nasdaqtrader",
                    source_symbol=sym,
                )
            )

    return listings


# JPX workbook columns are Japanese; match by substring so column reorders don't break us.
_JP_COLS: dict[str, str] = {
    "code": "コード",
    "name": "銘柄名",
    "segment": "市場・商品区分",
    "sector": "33業種区分",
}


def _jp_code(value: object) -> str:
    s = str(value).strip()
    if s.endswith(".0"):  # numeric Excel cells read back as e.g. "7203.0"
        s = s[:-2]
    return s.zfill(4) if s.isdigit() else s


def _jp_segment(seg: str) -> tuple[str, str | None, int | None]:
    """JPX 'market/product' string -> (security_type, segment_label, lot_size)."""
    if "ETF" in seg or "ETN" in seg:
        return ("etf", "ETF/ETN", None)
    if "REIT" in seg or "ファンド" in seg:
        return ("reit", "REIT/Fund", None)
    if "出資証券" in seg:
        return ("other", "Cooperative", None)
    if "プライム" in seg:
        return ("common", "Prime", 100)
    if "スタンダード" in seg:
        return ("common", "Standard", 100)
    if "グロース" in seg:
        return ("common", "Growth", 100)
    if "PRO" in seg:
        return ("common", "TOKYO PRO Market", 100)
    return ("other", seg or None, None)


def fetch_jp(*, force: bool = False) -> list[Listing]:
    """Japan universe from the JPX 'List of Issues' workbook."""
    path = _download(JPX_LISTED_URL, _CACHE_DIR / "jpx_data_j.xls", force=force)
    frame = pd.read_excel(path, dtype=object)
    cols = {key: next(c for c in frame.columns if sub in c) for key, sub in _JP_COLS.items()}

    listings: list[Listing] = []
    for record in frame.to_dict("records"):
        code = _jp_code(record[cols["code"]])
        if not code or code == "-":
            continue
        sec_type, segment, lot = _jp_segment(str(record[cols["segment"]] or ""))
        sector = str(record[cols["sector"]] or "").strip()
        listings.append(
            Listing(
                market="JP",
                ticker=code,
                name=str(record[cols["name"]] or "").strip() or None,
                exchange="TSE",
                mic="XTKS",
                security_type=sec_type,
                currency="JPY",
                cik=None,
                isin=None,
                lot_size=lot,
                sector=sector if sector and sector != "-" else None,
                segment=segment,
                source="jpx",
                source_symbol=code,
            )
        )
    return listings
