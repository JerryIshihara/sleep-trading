"""Canonical OHLCV input.

``CanonicalBars`` wraps a validated ``pd.DataFrame`` plus single-asset
metadata. It is the only input shape adapters accept; everything upstream
of the engine boundary funnels through here.

This is the public type that satisfies the ``BarFrame`` Protocol in
``src/strategy/`` — structurally, with no inheritance. Strategy code reads
``.frame``, ``.symbol``, ``.venue``, ``.interval``; it never imports this
concrete class.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from backtesting.errors import ValidationError

OHLCV_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")
ALLOWED_INTERVALS: frozenset[str] = frozenset(
    {"1s", "5s", "1m", "5m", "1h", "1d"}
)


@dataclass(frozen=True)
class CanonicalBars:
    """Validated OHLCV input for one (symbol, venue, interval) tuple.

    Construction does **not** validate — use :func:`validate` to build one
    safely from raw inputs. Direct construction is a fast path for internal
    callers (e.g. adapters re-wrapping a known-good frame).
    """

    frame: pd.DataFrame
    symbol: str
    venue: str
    interval: str


# ─── Public validator ──────────────────────────────────────────────


def validate(
    frame: pd.DataFrame,
    *,
    symbol: str,
    venue: str,
    interval: str,
) -> CanonicalBars:
    """Validate raw OHLCV input and return a :class:`CanonicalBars`.

    Rejects (raises :class:`ValidationError`):

    - non-string or empty ``symbol`` / ``venue``
    - ``interval`` outside the canonical set
    - non-:class:`pd.DataFrame` input
    - missing or extra columns (must be exactly ``open, high, low, close, volume``)
    - non-:class:`pd.DatetimeIndex`
    - naive datetime index (no tz)
    - non-UTC tz
    - non-monotonic or duplicate timestamps
    - non-``float64`` OHLCV columns (auto-coerced where lossless;
      raises otherwise)
    - NaN or +/-inf in OHLC
    - negative volume
    - ``high < max(open, close)`` or ``low > min(open, close)``

    NaN in ``volume`` is coerced to ``0.0``. The returned frame is a copy;
    callers may mutate without affecting the original.
    """
    _check_metadata(symbol, venue, interval)
    if not isinstance(frame, pd.DataFrame):
        raise ValidationError(
            f"frame must be pd.DataFrame, got {type(frame).__name__}"
        )

    cleaned = frame.copy()
    _check_columns(cleaned)
    _check_index(cleaned)
    cleaned = _coerce_dtypes(cleaned)
    _check_values(cleaned)
    _check_ohlc_consistency(cleaned)

    # Column order is canonical regardless of input ordering.
    cleaned = cleaned[list(OHLCV_COLUMNS)]
    return CanonicalBars(frame=cleaned, symbol=symbol, venue=venue, interval=interval)


# ─── Bar event → CanonicalBars bridge ──────────────────────────────


def bars_to_canonical_bars(bars: Iterable[Any]) -> CanonicalBars:
    """Convert an iterable of ``src/data`` ``Bar`` events into a CanonicalBars.

    Strict: rejects mixed ``symbol`` / ``venue`` / ``interval`` across the
    iterable, and validates the resulting frame the same way :func:`validate`
    does.

    Decimal prices/sizes are converted to ``float64`` here — that conversion
    is the documented precision boundary; downstream the canonical frame is
    float-typed throughout.
    """
    materialized = list(bars)
    if not materialized:
        raise ValidationError("bars_to_canonical_bars received an empty iterable")

    first = materialized[0]
    symbol = first.symbol
    venue = first.venue
    interval = first.interval
    if interval not in ALLOWED_INTERVALS:
        raise ValidationError(
            f"unknown interval {interval!r}; expected one of {sorted(ALLOWED_INTERVALS)}"
        )

    index: list[datetime] = []
    rows: list[tuple[float, float, float, float, float]] = []
    for i, bar in enumerate(materialized):
        if bar.symbol != symbol:
            raise ValidationError(
                f"mixed symbol at index {i}: expected {symbol!r}, got {bar.symbol!r}"
            )
        if bar.venue != venue:
            raise ValidationError(
                f"mixed venue at index {i}: expected {venue!r}, got {bar.venue!r}"
            )
        if bar.interval != interval:
            raise ValidationError(
                f"mixed interval at index {i}: expected {interval!r}, got {bar.interval!r}"
            )
        index.append(bar.ts_open)
        rows.append((
            float(bar.open),
            float(bar.high),
            float(bar.low),
            float(bar.close),
            float(bar.volume),
        ))

    df = pd.DataFrame(
        rows,
        index=pd.DatetimeIndex(index, name="ts_open"),
        columns=list(OHLCV_COLUMNS),
        dtype="float64",
    )
    return validate(df, symbol=symbol, venue=venue, interval=interval)


# ─── Internal checks ───────────────────────────────────────────────


def _check_metadata(symbol: str, venue: str, interval: str) -> None:
    # Runtime checks defend against callers ignoring the static signature.
    if not isinstance(symbol, str) or not symbol.strip():  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValidationError(f"symbol must be a non-empty string, got {symbol!r}")
    if not isinstance(venue, str) or not venue.strip():  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValidationError(f"venue must be a non-empty string, got {venue!r}")
    if interval not in ALLOWED_INTERVALS:
        raise ValidationError(
            f"interval must be one of {sorted(ALLOWED_INTERVALS)}, got {interval!r}"
        )


def _check_columns(frame: pd.DataFrame) -> None:
    cols = list(frame.columns)
    if set(cols) != set(OHLCV_COLUMNS):
        missing = sorted(set(OHLCV_COLUMNS) - set(cols))
        extra = sorted(set(cols) - set(OHLCV_COLUMNS))
        parts = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"extra {extra}")
        raise ValidationError(
            f"columns must be exactly {list(OHLCV_COLUMNS)}; {', '.join(parts)}"
        )


def _check_index(frame: pd.DataFrame) -> None:
    idx = frame.index
    if not isinstance(idx, pd.DatetimeIndex):
        raise ValidationError(
            f"index must be pd.DatetimeIndex, got {type(idx).__name__}"
        )
    if idx.tz is None:
        raise ValidationError("index must be tz-aware (UTC); got naive DatetimeIndex")
    # tz comparison is by zone identity; coerce to UTC if user passed a different UTC alias.
    utc_offset = idx.tz.utcoffset(None)
    if utc_offset is None or utc_offset.total_seconds() != 0:
        raise ValidationError(f"index tz must be UTC; got {idx.tz!r}")
    if not idx.is_monotonic_increasing:
        raise ValidationError("index must be strictly monotonic increasing")
    if idx.has_duplicates:
        dupes = idx[idx.duplicated()][:5].tolist()
        raise ValidationError(
            f"index must have unique timestamps; duplicates include {dupes}"
        )


def _coerce_dtypes(frame: pd.DataFrame) -> pd.DataFrame:
    for col in OHLCV_COLUMNS:
        if frame[col].dtype != np.float64:
            try:
                frame[col] = frame[col].astype("float64")
            except (TypeError, ValueError) as e:
                raise ValidationError(
                    f"column {col!r} cannot be coerced to float64: {e}"
                ) from e
    return frame


def _check_values(frame: pd.DataFrame) -> None:
    for col in ("open", "high", "low", "close"):
        s = frame[col]
        if s.isna().any():
            n_bad = int(s.isna().sum())
            raise ValidationError(f"column {col!r} has {n_bad} NaN values (none allowed in OHLC)")
        if np.isinf(s.to_numpy()).any():
            raise ValidationError(f"column {col!r} contains +/-inf")

    vol = frame["volume"]
    if np.isinf(vol.to_numpy()).any():
        raise ValidationError("column 'volume' contains +/-inf")
    if (vol.fillna(0.0) < 0).any():
        n_bad = int((vol.fillna(0.0) < 0).sum())
        raise ValidationError(f"column 'volume' has {n_bad} negative values")
    if vol.isna().any():
        frame["volume"] = vol.fillna(0.0)


def _check_ohlc_consistency(frame: pd.DataFrame) -> None:
    o, h, lo, c = (frame[k].to_numpy() for k in ("open", "high", "low", "close"))
    bad_high = h < np.maximum(o, c)
    bad_low = lo > np.minimum(o, c)
    if bad_high.any():
        idx = int(np.argmax(bad_high))
        raise ValidationError(
            f"bar {idx}: high ({h[idx]}) < max(open, close) ({max(o[idx], c[idx])})"
        )
    if bad_low.any():
        idx = int(np.argmax(bad_low))
        raise ValidationError(
            f"bar {idx}: low ({lo[idx]}) > min(open, close) ({min(o[idx], c[idx])})"
        )


__all__ = [
    "ALLOWED_INTERVALS",
    "OHLCV_COLUMNS",
    "CanonicalBars",
    "bars_to_canonical_bars",
    "validate",
]
