"""Exception hierarchy.

All backtest errors derive from ``BacktestError``. Callers should expect
fully-populated results or a typed exception — never a partial result.
"""

from __future__ import annotations


class BacktestError(Exception):
    """Base class for everything raised by this package."""


class ValidationError(BacktestError):
    """Input bars, targets, or config violate the canonical schema.

    Raised by validators at module boundaries before any engine runs.
    """


class UnsupportedFeatureError(BacktestError):
    """A strategy uses a feature the requested adapter does not support.

    Raised up front during capability gating, before any engine runs, so
    partial-result states cannot exist.
    """

    backend: str
    feature: str
    detail: str | None

    def __init__(self, backend: str, feature: str, *, detail: str | None = None):
        msg = f"backend {backend!r} does not support feature {feature!r}"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)
        self.backend = backend
        self.feature = feature
        self.detail = detail


class AdapterError(BacktestError):
    """Adapter-level translation failed.

    Wraps the engine-native exception so engine-specific types never escape
    the adapter boundary.
    """

    backend: str
    __cause__: BaseException | None

    def __init__(self, backend: str, message: str, *, cause: BaseException | None = None):
        super().__init__(f"adapter {backend!r}: {message}")
        self.backend = backend
        self.__cause__ = cause


class ReconciliationError(BacktestError):
    """Reconciler couldn't run (e.g. fewer than 2 adapters succeeded)."""


# ─── Backtest lifecycle errors ──────────────────────────────────────


class BacktestNotRunError(BacktestError):
    """``get_report()`` was called before ``run()``."""


class BacktestFailedError(BacktestError):
    """``get_report()`` was called on a Backtest whose ``run()`` raised.

    Carries the original exception as ``__cause__``.
    """

    __cause__: BaseException | None

    def __init__(self, cause: BaseException):
        super().__init__(f"backtest failed: {cause!r}")
        self.__cause__ = cause


class AlreadyRanError(BacktestError):
    """``run()`` was called on a Backtest that has already executed.

    Backtest objects are single-shot: re-running is a programming error.
    Build a fresh Backtest from the same Strategy instance instead.
    """

    state: str

    def __init__(self, state: str):
        super().__init__(f"Backtest already in state {state!r}; build a fresh one to re-run")
        self.state = state


__all__ = [
    "AdapterError",
    "AlreadyRanError",
    "BacktestError",
    "BacktestFailedError",
    "BacktestNotRunError",
    "ReconciliationError",
    "UnsupportedFeatureError",
    "ValidationError",
]
