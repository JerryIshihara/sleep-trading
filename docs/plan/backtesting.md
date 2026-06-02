# Backtesting — plan

## Context

The strategy / features / risk layers aren't built yet, but we already know the first thing they'll need: a backtest harness that produces results we can trust. Writing a single battle-tested event-driven engine from scratch is years of work and a great way to ship undetected look-ahead bias. Instead this layer wraps three mature open-source engines — **VectorBT** (vectorized), **Backtesting.py** (simple event-driven), **Backtrader** (full event-driven) — behind one Strategy + Config + Result interface and **runs the same strategy through all of them in parallel**. Disagreement between engines is evidence: fill-count mismatch points to a timing or translation bug, equity-curve drift points to slippage / sizing / accounting divergence, and single-engine outliers point to backend quirks. Cross-engine agreement is valuable, but it is not the correctness oracle by itself; the oracle is the canonical execution contract below. See [`../research/backtesting/survey.md`](../research/backtesting/survey.md) for why these three.

The layer is intentionally separate from the live strategy code path. Live strategies will consume from `DataClient` per [`data.md`](./data.md); the backtest engine consumes `CanonicalBars`, a small wrapper around one canonical OHLCV `pd.DataFrame` plus single-asset metadata (`symbol`, `venue`, `interval`). A `bars_to_canonical_bars(Iterable[Bar])` helper bridges from `src/data/events.py` `Bar` events into that public input type. Once `ReplayAdapter` lands, the bridge becomes the integration seam.

## Design goals

1. **One strategy definition, many engines.** A `Strategy` subclass runs unchanged on every supported engine. Adapters translate one canonical target-position contract to each engine's native API.
2. **Cross-checking is the whole point.** The default workflow is `reconcile.run_all(strategy, bars, config)`, not single-engine runs. A pass/warn/fail diff table is the primary output.
3. **No look-ahead, enforced at the seam.** The target at bar `t` may use only data through `t` and fills at `t+1` open. Adapters enforce the fill timing; prefix-invariance tests catch target generators that leak future rows.
4. **Backend-agnostic results.** Headline metrics (Sharpe, Sortino, Calmar, max DD) are recomputed by us from normalized fills, trades, and equity curves, so disagreements are real divergence, not different trading-days-per-year conventions.
5. **Strict canonical input.** One public `CanonicalBars` type whose `frame` is a tz-aware UTC OHLCV `pd.DataFrame` with lowercase `float64` columns plus explicit `symbol`, `venue`, `interval` metadata. Validators reject naive datetimes, non-monotonic index, NaNs in OHLC, negative volume, or mixed-asset input.
6. **Unit-testable without network or vendor data.** Synthetic fixtures (linear ramp, sine overlay) give known-result baselines.

## Versions

- **v1** — first shipping iteration. Target-position-only `Strategy` API. Three engines: VectorBT, Backtesting.py, Backtrader. Portable core = discrete long / flat / short targets with next-open market fills; declarative `ExitRules` land after core parity and are capability-gated. Reconciliation across scalars, equity curve, fill list, trade list. Single-asset only. Demoable via CLI.
- **v2** — extensions on the v1 contract. Adds event-driven `EventStrategy` ABC with `on_bar` callbacks (event-driven engines only; VectorBT skipped with warning). Walk-forward harness. Integration with `src/data` `ReplayAdapter` / `DataClient`. Parameter-sweep helper delegating to VectorBT's vectorized form.

v2 doesn't replace v1, it extends. v1 strategies keep running on v2 code unchanged.

---

# v1

## v1 goal

Ship a unified backtesting engine at `src/backtest/` that takes one `Strategy` subclass, runs it through VectorBT + Backtesting.py + Backtrader in parallel, and emits a reconciliation report that flags inter-engine disagreement against per-metric tolerance thresholds. Single-asset only. Target-position Strategy API only. The MVP proves the canonical execution contract first; declarative exits are added only after the core long / flat / short path reconciles cleanly.

## v1 design decisions

1. **Strategy API: target-position only.** Strategies return a `pd.Series` of discrete `PositionTarget` values in `{-1, 0, +1}`. `+1` means fully long, `0` means flat, `-1` means fully short. This is deliberately **not** an action / no-op signal API; `0` closes exposure. Fractional rebalancing semantics are not v1.
2. **Canonical input data: `CanonicalBars`.** The public API carries a validated OHLCV `pd.DataFrame` plus `symbol`, `venue`, and `interval`. The frame uses a tz-aware UTC `DatetimeIndex` keyed by `ts_open`, with columns `["open","high","low","close","volume"]` as `float64`. `Decimal` doesn't roundtrip through any of the three frameworks; `float64` is precise enough at the metric level.
3. **Single asset only.** Multi-asset adds Nx complexity per adapter and target-array rebalancing semantics differ across engines.
4. **`next_open` fill policy only.** The only unambiguous mapping across all three engines.
5. **`full_notional` position sizing only.** A discrete target maps to one canonical exposure state: fully long, flat, or fully short. Cross-engine determinism requires one canonical default before fractional sizing exists.
6. **Shorts allowed (`-1` targets), borrow fees not modeled.** All three engines support shorts; borrow modeling diverges sharply.
7. **Normalized fills are the primitive artifact.** Each backend returns one canonical `fill_list`; `trade_list`, realized P&L, and headline metrics are derived from fills plus the normalized `equity_curve`. Backend-native scalars go in `raw_metrics` as a debugging escape hatch.
8. **Capabilities are validated before a run.** A backend that cannot faithfully support a requested feature fails fast during adapter validation; the unified API must never silently degrade.
9. **Per-metric thresholds for reconciliation, not statistical tests.** Defaults: total return ±50 bps absolute, Sharpe ±0.15, max DD ±50 bps, equity-curve max pointwise relative deviation ≤ 0.5% after warmup, **fill count exact match** for target-position strategies — any difference is real divergence. Tunable per-test via `Tolerance`.

## v1 canonical execution semantics

The unified API is only useful if every backend implements the same semantics:

1. `CanonicalBars.frame.index` is the bar **open** timestamp (`ts_open`), tz-aware UTC. One `CanonicalBars` value contains exactly one symbol, one venue, and one interval.
2. `generate_targets()` returns one target per input bar. Target `t` may depend only on bars through `t`; tests enforce prefix invariance (`targets(bars[:t+1]) == targets(bars)[:t+1]`) so a vectorized implementation cannot quietly leak future rows.
3. `+1`, `0`, `-1` mean long, flat, short. `0` is an explicit flat target, never “hold previous position.”
4. If target exposure after bar `t` differs from current exposure, the adapter schedules the required market fill(s) for `open[t+1]`. A target change on the final bar produces no new fill because no `t+1` open exists.
5. A direct flip (`-1 -> +1` or `+1 -> -1`) is canonicalized as **close then reopen** at the same next open. It appears as two fills so reversals reconcile deterministically.
6. Worse-side slippage is applied to the raw fill price first; commission is then computed on slipped notional. All adapters normalize to that order.
7. Any position still open after the last tradable bar is force-closed at the final close with `exit_reason="end_of_data"` so result normalization is deterministic. This is the only v1 accounting exception to the next-open fill rule.
8. Declarative `ExitRules` are a later v1 extension on top of the core target-position model, not a prerequisite for proving the core. When enabled:
   - trailing references update only after completed bars;
   - `max_bars_held` schedules a next-open close after the Nth held bar closes;
   - if OHLC data makes multiple intrabar exits possible and the path is unknowable, use a deterministic conservative convention: the least favorable valid fill for the open position wins;
   - gap-through exits fill at the first available worse price, not optimistically at the trigger price.

## v1 unified API contract

The "unified" half of "unified backtesting engine" is this section. Every adapter consumes the same inputs and produces the same outputs; the strategy author and the reconciler only see these canonical shapes. Engine-native types live behind the adapter boundary and never leak out. The abstractions below (next section) are the code shapes that implement these contracts.

### Data flow

```
src/data/events.py Bar             ─┐
                                    ├─► bars_to_canonical_bars() ─► CanonicalBars ──────┐
external Parquet / CSV / DataFrame ─┘                                                   │
                                                                                        ▼
                              Strategy.generate_targets(CanonicalBars) ─► TargetSeries ─┤
                                                                                        ▼
                                                BacktestConfig + Tolerance ─────────────┤
                                                                                        ▼
                                          engine.run_backtest(strategy, bars, config, backend)
                                                                  │
                                                                  ▼
                                                   Adapter.run() ──► (native engine call)
                                                                  │
                                                                  ▼
                                              raw equity + raw fills from engine
                                                                  │
                                                                  ▼
                                  canonical BacktestResult (equity_curve + fill_list + trade_list)
                                                                  │
                                                                  ▼
                                            metrics.py recomputes Sharpe / Sortino / Calmar / DD
                                                                  │
                                                                  ▼
                                                          BacktestResult (full)
                                                                  │
                                                                  ▼
                                          reconcile.run_all() ──► ReconciliationReport
```

The canonical schemas at each arrow are specified below. **No adapter or strategy ever sees an engine-native type.**

### Canonical bars input (`CanonicalBars`)

`CanonicalBars` carries `symbol`, `venue`, `interval`, and one canonical OHLCV `frame`.

`CanonicalBars.frame` is a `pd.DataFrame` with these exact requirements:

| Column     | Dtype                                  | Constraint |
|------------|----------------------------------------|------------|
| _(index)_  | `pd.DatetimeIndex`, tz-aware UTC       | strictly monotonic increasing; no duplicates |
| `open`     | `float64`                              | finite; no NaN |
| `high`     | `float64`                              | finite; no NaN; `>= max(open, close)` |
| `low`      | `float64`                              | finite; no NaN; `<= min(open, close)` |
| `close`    | `float64`                              | finite; no NaN |
| `volume`   | `float64`                              | `>= 0`; NaN coerced to `0.0` by validator |

Validators reject: naive datetime index, non-UTC tz, non-monotonic or duplicate timestamps, NaN/inf in OHLC, negative volume, missing columns, extra columns, or mixed `symbol` / `venue` / `interval` input. `validate(df, *, symbol, venue, interval)` returns a cleaned `CanonicalBars` object or raises `ValidationError` with a precise reason. Downstream code assumes the wrapper and frame are clean.

### Target Series (output of `Strategy.generate_targets`)

`pd.Series` with these exact requirements:

- **dtype** numeric and losslessly coercible to `int8`
- **index identical** to the input `CanonicalBars.frame.index` — same length, same timestamps, same tz
- **values exactly in `{-1, 0, +1}`** — checked at engine entry; any other value raises `ValidationError`
- **NaN allowed only in the first `strategy.warmup_bars`** positions; NaN after warmup is a strategy bug
- **semantics**: value at bar `t` is the desired discrete exposure after bar `t` closes. The engine schedules the required transition at bar `t+1` open. `+1` means fully long, `0` means flat, `-1` means fully short. `0` is never a no-op / hold signal.

### Fill list DataFrame (canonical primitive)

`pd.DataFrame` with these exact columns:

| Column           | Dtype                                  | Notes |
|------------------|----------------------------------------|-------|
| `ts`             | tz-aware UTC `datetime64[ns, UTC]`     | timestamp where the fill happened |
| `side`           | `string`, `{"buy", "sell"}`           | execution side |
| `qty`            | `float64`                              | absolute quantity; always positive |
| `px`             | `float64`                              | actual fill price including slippage |
| `fee`            | `float64`                              | commission paid on this fill |
| `reason`         | `string`                               | one of `{"target_change", "stop_loss", "take_profit", "trailing_stop", "max_bars_held", "end_of_data"}` |
| `order_group_id` | `int64`                                | same id for related fills from one canonical transition, e.g. a reversal |

Sort order: ascending by `ts`, then canonical transition order within a timestamp (close fill before reopen fill on a reversal). Fills are the lowest-level normalized artifact; derived trades must be reproducible from this table.

### Trade list DataFrame (canonical)

`pd.DataFrame` with these exact columns:

| Column         | Dtype                                  | Notes |
|----------------|----------------------------------------|-------|
| `entry_ts`     | tz-aware UTC `datetime64[ns, UTC]`     | bar timestamp where the entry fill happened |
| `exit_ts`      | tz-aware UTC `datetime64[ns, UTC]`     | exit bar timestamp; every v1 trade is closed because open positions receive an `end_of_data` fill |
| `side`         | `string`, `{"long", "short"}`          | direction |
| `entry_px`     | `float64`                              | actual fill price including slippage |
| `exit_px`      | `float64`                              | actual fill price including slippage |
| `size`         | `float64`                              | absolute quantity (always positive); shares/contracts/coins |
| `pnl`          | `float64`                              | gross P&L in cash; positive = profit; net of commission |
| `return_pct`   | `float64`                              | per-trade return as fraction (e.g. `0.0123`); sign-aware for shorts |
| `bars_held`    | `int64`                                | bars from entry (inclusive) to exit (exclusive) |
| `exit_reason`  | `string`                               | one of `{"target_change", "stop_loss", "take_profit", "trailing_stop", "max_bars_held", "end_of_data"}` |

Sort order: ascending by `entry_ts`. Index is a default `RangeIndex` (trades aren't time-indexed; multiple trades can start on the same bar).

### Equity curve Series (canonical)

`pd.Series` with these exact requirements:

- **dtype** `float64`
- **index identical** to the input `CanonicalBars.frame.index`
- **value at bar `t`** = mark-to-market portfolio value after bar `t` close, including any fills that occurred at bar `t` open and unrealized PnL on the open position at bar `t` close
- **value at bar 0** = `float(config.initial_cash)`
- **no NaN, no negative values, no inf**

### Adapter contract

Every `Adapter.run(strategy, bars, config) -> BacktestResult`:

**MUST**
1. Accept only validated `CanonicalBars` on the public engine path (or document the private path that constructs one via `validate(...)`).
2. Call `strategy.generate_targets(bars)` exactly once; cache the result for reuse.
3. Enforce the canonical execution semantics above: target at bar `t` fills at bar `t+1` open, final-bar target changes do not create fills, and reversals emit close-then-open fills in canonical order.
4. Apply `config.commission_bps` and `config.slippage_bps` exactly once. Slippage is worse-side (buy fills higher, sell fills lower).
5. Return a `BacktestResult` with `equity_curve`, `fill_list`, and derived `trade_list` populated to the canonical schemas above. `raw_metrics` may be empty `{}` but the field must exist.
6. Surface adapter-level errors as `AdapterError` carrying the engine name and the underlying engine exception. Engine-native exceptions must not escape.

**MUST NOT**
1. Mutate the input `bars`, `strategy`, or `config`.
2. Read filesystem or network. Adapters are pure functions of `(strategy, bars, config)`.
3. Apply slippage twice (once in canonical post-processing + once via engine config). Pick one path.
4. Insert phantom fills at the start (warmup) or end (off-by-one padding) of the series.
5. Recompute headline metrics (Sharpe, Sortino, etc.) — those are filled by `metrics.py` from canonical fills, derived trades, and the normalized equity curve. The adapter only produces the normalized artifacts.

### AdapterCapabilities

```python
@dataclass(frozen=True)
class AdapterCapabilities:
    supports_short: bool                  # accepts target -1
    supports_stop_loss: bool              # honors ExitRules.stop_loss_pct
    supports_take_profit: bool            # honors ExitRules.take_profit_pct
    supports_trailing_stop: bool          # honors ExitRules.trailing_stop_pct
    supports_max_bars_held: bool          # honors ExitRules.max_bars_held
    supports_event_driven: bool           # accepts EventStrategy (v2; False for VectorBT)
    intrabar_fills: bool                  # True iff engine fills stops at the stop price within a bar
                                          # (False = stops fill at next bar open instead)
```

The engine consults `capabilities` before dispatching: if `strategy.exits.trailing_stop_pct is not None` and `adapter.capabilities.supports_trailing_stop is False`, `engine.run_backtest` raises `UnsupportedFeatureError` immediately. Silent degradation is forbidden — cross-checking against a silently-degraded adapter is worse than no cross-check.

### Error model

| Exception              | Raised by               | Meaning |
|------------------------|-------------------------|---------|
| `ValidationError`      | `data.validate`, engine entry | input bars, targets, or config violate the canonical schema |
| `UnsupportedFeatureError` | `engine.run_backtest` | strategy uses a feature the requested adapter does not support |
| `AdapterError`         | adapter                 | adapter-level translation failed; wraps the engine-native exception |
| `ReconciliationError`  | `reconcile.run_all`     | reconciler couldn't run (e.g. fewer than 2 adapters succeeded) |

All errors raised before any partial result is returned. Callers see exceptions or fully-populated `BacktestResult` / `ReconciliationReport` objects — never partials.

## v1 backtest job flow

The unified API contract above specifies what one backtest run looks like end-to-end. This section specifies the orchestration *around* one run: how a fully constructed `Strategy` plus caller-supplied bars / config becomes a `BacktestJob`, how the runner dispatches it through the unified API across all requested adapters, and where the resulting `ReconciliationReport` goes. v1 is in-process and synchronous, matching `data.md`'s single-process Phase 1 stance — promotion to a queue or worker pool is a v3 concern, gated on a real backlog.

### End-to-end orchestration

```
          caller owns:
          ─ fully constructed Strategy instance
          ─ bars input (Parquet path / Iterable[Bar] / CanonicalBars)
          ─ BacktestConfig + optional metadata
                              │
                              ▼
          BacktestJob.from_strategy(strategy, bars=..., **overrides)
          ─ resolves bars input → validated CanonicalBars
          ─ binds BacktestConfig + Tolerance
          ─ selects backends (default: all three)
          ─ attaches report sinks
                              │
                              ▼  runner.dispatch(job)
          BacktestJobRunner
          ─ re-validates CanonicalBars (defense in depth)
          ─ checks AdapterCapabilities vs Strategy needs
            (raises UnsupportedFeatureError up front, before any engine runs)
          ─ delegates to reconcile.run_all(...)
                              │
                              ▼
   ┌──────────────┬────────────────┬──────────────┐
   │  VectorBT    │ Backtesting.py │  Backtrader  │   ← unified API contract applies here
   │  adapter     │  adapter       │  adapter     │     (canonical inputs in, canonical
   └──────┬───────┴────────┬───────┴──────┬───────┘      BacktestResult out)
          │                │              │
          └────────────────┼──────────────┘
                           │ each adapter returns BacktestResult
                           ▼
          metrics.py recomputes per-result scalars
          reconcile.py compares ──► ReconciliationReport
                           │
                           ▼  for each sink in job.sinks
   ┌──────────────────┬───────────────────┬────────────────────────────┐
   │  StdoutSink      │  JsonFileSink     │  CallbackSink              │
   │  (CLI default)   │  (dashboard, CI)  │  (caller-owned follow-up)  │
   └──────────────────┴───────────────────┴────────────────────────────┘
                           │
                           ▼
          ReconciliationReport returned to the caller
```

The dashed-box "unified API" region is exactly what `## v1 unified API contract` specifies; the surrounding boxes are the job-orchestration layer that this section adds.

### BacktestJob

```python
@dataclass(frozen=True)
class BacktestJob:
    job_id: UUID                              # generated at construction; stable across retries
    strategy: Strategy                        # already instantiated; params bound
    bars: CanonicalBars                       # already validated
    config: BacktestConfig
    tolerance: Tolerance = Tolerance()
    backends: tuple[str, ...] = ("vectorbt", "backtesting_py", "backtrader")
    sinks: tuple[ReportSink, ...] = ()        # where the ReconciliationReport goes after dispatch
    metadata: dict[str, Any] = field(default_factory=dict)  # caller-supplied labels / provenance

    @classmethod
    def from_strategy(
        cls,
        strategy: Strategy,
        *,
        bars: CanonicalBars | Iterable[Bar] | Path,
        config: BacktestConfig | None = None,
        tolerance: Tolerance | None = None,
        backends: tuple[str, ...] | None = None,
        sinks: tuple[ReportSink, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> "BacktestJob":
        """Resolve strategy + bars into a runnable job.

        Bars may arrive as a Parquet path, an Iterable[Bar], or a pre-built
        CanonicalBars. This method normalizes all three paths via the existing
        validators / bars_to_canonical_bars.
        """
```

`BacktestJob` is **frozen and self-contained**: once constructed, it carries everything the runner needs. Retries replay the same `job_id` for traceability.

### BacktestJobRunner contract

```python
class BacktestJobRunner:
    def dispatch(self, job: BacktestJob) -> ReconciliationReport: ...
    async def dispatch_async(self, job: BacktestJob) -> ReconciliationReport: ...
```

`dispatch` is the v1 happy path: synchronous, single-process, one job at a time. Internally:

1. **Re-validate** `job.bars` via the same validator the strategy module called. The strategy module may have built `CanonicalBars` from raw data that wasn't validated; the runner does not trust the boundary.
2. **Capability gate** — for each `backend in job.backends`, check `adapter.capabilities` against the strategy's declared feature use (`strategy.exits` fields, `requires_event_driven` flag in v2, etc.). Raise `UnsupportedFeatureError` *before any engine runs* so partial results never leak.
3. **Delegate** to `reconcile.run_all(job.strategy, job.bars, job.config, backends=job.backends, tolerance=job.tolerance)`. This is the only path from job to engines — no parallel route.
4. **Emit** to every sink in `job.sinks`. Sinks are fire-and-forget per-sink: a single sink failure logs but does not block the other sinks or corrupt the returned report.
5. **Return** the `ReconciliationReport` to the caller.

`dispatch_async` exists for future runner ergonomics. In v1 it may stub as `await asyncio.to_thread(self.dispatch, job)`; v2 can make it first-class when async backtest inputs are introduced without changing the job / runner split.

### Strategy module ↔ backtest module seam

The dependency direction is fixed: **`src/backtest/` imports from `src/strategy/`; `src/strategy/` never imports from `src/backtest/`.** Strategies must remain authorable, runnable live, and unit-testable without the backtest package installed.

`src/strategy/protocol.py` owns the contract — `Strategy` ABC, `ExitRules`, `PositionTarget`, and the `BarFrame` Protocol. `src/backtest/bars.py` defines `CanonicalBars`, which satisfies `BarFrame` structurally (no inheritance, no import either way). This is the seam that keeps the graph acyclic.

| Strategy module exports                              | Backtest module consumes                                  |
|------------------------------------------------------|-----------------------------------------------------------|
| `Strategy` ABC + `ExitRules` + `BarFrame` Protocol   | imported at module level by `backtest.backtest`, adapters |
| `Strategy` subclass instance, fully constructed      | accepts via `BacktestJob.strategy`; no introspection inside |
| `warmup_bars`, `exits` set on the strategy           | read via the public attrs of the `Strategy` ABC           |

Everything else needed to run a backtest — bars, config, tolerance, backends, sinks, metadata — is supplied by the caller to `BacktestJob.from_strategy(...)`, not imported from the strategy module.

`src/backtest/` makes **no assumptions about how a strategy was discovered** — grid search, ML, human-authored, or hand-written. It depends only on the public `Strategy` contract. If a research workflow exists upstream, it must first materialize a `Strategy`; the backtest module never imports, names, or knows about research artifacts.

### Report sinks

```python
class ReportSink(Protocol):
    def emit(self, report: ReconciliationReport, job: BacktestJob) -> None: ...
```

v1 ships three:
- **`StdoutSink`** — colored pass/warn/fail table; default for CLI invocations.
- **`JsonFileSink(directory)`** — writes `{directory}/{job_id}.json` with `report.to_dict()` for the dashboard and CI.
- **`CallbackSink(callback)`** — invokes a caller-owned `callback(report, job)` for follow-up actions without `src/backtest/` knowing who consumes the report.

Sinks are configured per-job (not globally) so different jobs route differently — a `cli run --reconcile` invocation defaults to `StdoutSink`, while an application-level caller may wire `CallbackSink` + `JsonFileSink`. A failing sink raises into the runner's log but the returned `ReconciliationReport` is unaffected; the runner never swallows a report just because a sink couldn't persist it.

### Module additions for job flow

Beyond the v1 module layout below, the job flow adds one file:

```
src/backtest/
  sleep_trading_backtest/
    job.py                          # BacktestJob, BacktestJobRunner, ReportSink, StdoutSink,
                                    # JsonFileSink, CallbackSink
```

`engine.py` and `reconcile.py` stay focused on the per-run unified-API surface; `job.py` is the orchestration layer that calls them. CLI (`cli.py`) constructs a `BacktestJob` from argv and dispatches via `BacktestJobRunner`.

## v1 abstractions

### Strategy (owned by `src/strategy/`, not by backtest)

`Strategy`, `ExitRules`, `PositionTarget`, and the `BarFrame` Protocol live in `src/strategy/protocol.py`. They are not part of `src/backtest/`. `src/backtest/` imports them; `src/strategy/` does **not** import anything from `src/backtest/`. This keeps strategies authorable, runnable live, and testable without the backtest package being installed at all.

For reference, the shape backtest depends on (defined upstream):

```python
# src/strategy/protocol.py — not edited by backtest

class BarFrame(Protocol):
    """Anything a Strategy can read its bars from.

    CanonicalBars (backtest input) and the eventual live-mode adapter both
    satisfy this. Strategy code never imports the concrete class.
    """
    symbol: str
    venue: str
    interval: str
    frame: pd.DataFrame                 # tz-aware UTC index, OHLCV float64 columns

@dataclass(frozen=True)
class ExitRules:
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_stop_pct: float | None = None
    max_bars_held: int | None = None

PositionTarget = Literal[-1, 0, 1]

class Strategy(ABC):
    """Target-position unified strategy.

    No look-ahead: target at bar t may only use bars[:t+1]; fill happens at t+1 open.
    """
    name: str
    warmup_bars: int = 0
    exits: ExitRules | None = None

    @abstractmethod
    def generate_targets(self, bars: BarFrame) -> pd.Series:
        """Indexed identically to bars.frame; values in {-1, 0, +1}. NaN forbidden after warmup."""
```

`CanonicalBars` in `src/backtest/bars.py` happens to satisfy `BarFrame` structurally — no import or inheritance relationship in either direction. This is the no-cycle seam.

### Canonical data

```python
@dataclass(frozen=True)
class CanonicalBars:
    frame: pd.DataFrame
    symbol: str
    venue: str
    interval: Literal["1s", "5s", "1m", "5m", "1h", "1d"]

def validate(df: pd.DataFrame, *, symbol: str, venue: str, interval: str) -> CanonicalBars: ...
def bars_to_canonical_bars(bars: Iterable[Bar]) -> CanonicalBars: ...
```

`Bar` is imported from `src/data/events.py` (prerequisite — see execution order step 0).

### Config

```python
@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: Decimal
    commission_bps: float = 0.0
    slippage_bps: float = 0.0                              # worse-side fill price
    fill_policy: Literal["next_open"] = "next_open"
    position_sizing: Literal["full_notional"] = "full_notional"
    allow_short: bool = True

@dataclass(frozen=True)
class Tolerance:
    total_return_bps: float = 50.0
    sharpe_abs: float = 0.15
    max_drawdown_bps: float = 50.0
    equity_curve_max_rel_dev: float = 0.005
    fill_count_must_match_exactly: bool = True
    trade_count_must_match_exactly: bool = True
```

### Adapter

```python
class Adapter(Protocol):
    name: str
    capabilities: AdapterCapabilities      # supports_short, supports_trailing_stop, ...
    def validate(self, strategy: Strategy, bars: CanonicalBars, config: BacktestConfig) -> CapabilityReport: ...
    def run(self, strategy: Strategy, bars: CanonicalBars, config: BacktestConfig) -> BacktestResult: ...
```

Three implementations (~80–150 LOC each):

- **VectorBT** — compute `targets = strategy.generate_targets(bars)`, derive canonical order timestamps from target transitions, and pass engine inputs so every transition fills exactly at the required next open. Do **not** rely on an undocumented combination of shifted targets and shifted prices; adapter tests pin the timing against golden fills. Extract `pf.value()` as equity and normalize engine records to canonical fills.
- **Backtesting.py** — pre-compute `self._targets = strategy.generate_targets(bars).values` in `__init__`; `next()` reads the target visible for the completed bar and places the next canonical order transition. `Backtest(df_renamed, _Wrap, cash=…, commission=bps/1e4, exclusive_orders=True)`. No built-in slippage — adapter code applies canonical worse-side fill pricing. Extract the equity curve and normalize fills.
- **Backtrader** — `bt.Strategy` with pre-computed targets on `__init__`; `next()` translates the current canonical target into order transitions, with custom slippage / sizing normalization where needed. `bt.feeds.PandasData(dataname=bars.frame)`, `cerebro.broker.setcash`, `setcommission(commission=bps/1e4)`. Capture native orders / analyzers, then normalize to canonical fills and equity.

### Result

```python
@dataclass(frozen=True)
class BacktestResult:
    backend: str
    total_return: float
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    max_drawdown_duration: pd.Timedelta
    win_rate: float
    profit_factor: float
    exposure_pct: float
    equity_curve: pd.Series                # float64, UTC index
    fill_list: pd.DataFrame                # ts, side, qty, px, fee, reason, order_group_id
    trade_list: pd.DataFrame               # derived from fills: entry_ts, exit_ts, side,
                                           # entry_px, exit_px, size, pnl, return_pct,
                                           # bars_held, exit_reason
    raw_metrics: dict                      # backend-native dict; debugging only
```

Scalars are always recomputed by `metrics.py` from canonical fills, derived trades, and the normalized equity curve. `raw_metrics` is debug-only. Annualization derives from `CanonicalBars.interval` unless a future config override says otherwise.

### Reconciler

```python
def run_all(strategy, bars, config,
            backends=("vectorbt", "backtesting_py", "backtrader"),
            tolerance: Tolerance = Tolerance()) -> ReconciliationReport: ...
```

Pairwise comparison against thresholds. `ReconciliationReport` carries per-metric pass/warn/fail, a color-coded diff table, per-engine `BacktestResult` set, mismatched-fill list, mismatched-trade list, and one overall verdict.

Failure modes the reconciler is designed to surface:
- **Fill-count or fill-timestamp mismatch** → timing / translation bug against the canonical execution contract.
- **Equity divergence growing over time** → compounding drift from slippage application order.
- **Single-bar discontinuity at the first fill** → off-by-one in next-open scheduling.
- **Two engines agree, one disagrees** → engine quirk, not strategy bug.

Look-ahead inside a vectorized strategy is caught separately by the prefix-invariance validator; cross-engine agreement alone cannot prove a target generator is causal.

## v1 module layout

```
src/backtest/
  pyproject.toml                    # name = "sleep-trading-backtest"
  README.md
  sleep_trading_backtest/
    __init__.py
    config.py                       # BacktestConfig, Tolerance
    result.py                       # BacktestResult, Fill, Trade, ReconciliationReport
    data.py                         # CanonicalBars, validators, bars_to_canonical_bars()
    metrics.py                      # Sharpe/Sortino/Calmar/max-DD recomputation
    engine.py                       # run_backtest(strategy, bars, config, backend)
    reconcile.py                    # run_all(...) -> ReconciliationReport
    job.py                          # BacktestJob, BacktestJobRunner, ReportSink + 3 sinks
    cli.py                          # python -m sleep_trading_backtest.cli ...
    adapters/
      base.py                       # Adapter Protocol + AdapterCapabilities
      vectorbt_adapter.py
      backtesting_py_adapter.py
      backtrader_adapter.py
    strategies/                     # reference / test strategies
      buy_and_hold.py
      sma_crossover.py
  tests/
    fixtures/
      synthetic_ramp_1m.parquet     # linear ramp, sanity baseline
      synthetic_sine_1m.parquet     # sine overlay, targets change
    test_canonical_data.py
    test_metrics.py
    test_buy_and_hold_parity.py     # identical across all backends
    test_sma_crossover_parity.py    # within tolerance across all backends
    test_quirk_regressions.py
    test_reconciler.py
```

Matches the existing `src/data/` shape: own pyproject, package directory, tests alongside.

## v1 execution order

0. **Prerequisite (in `src/data/`):** implement `Bar`, `Tick`, `Trade`, `OrderbookLevel`, `Side`, `Event` union in `src/data/events.py` per [`../architecture/data-module.md`](../architecture/data-module.md) §2. Pure dataclasses, no I/O. This is step 1 of [`data.md`](./data.md) anyway and unblocks everything downstream, not just backtest.
0a. **Prerequisite (in `src/strategy/`):** define `Strategy` ABC, `ExitRules`, `PositionTarget`, and the `BarFrame` Protocol in `src/strategy/protocol.py`. Pure ABC + dataclasses + Protocol; no imports from `src/backtest/`. Backtest cannot scaffold until this exists, since `Backtest.from_strategy(strategy: Strategy, ...)` requires the symbol.
1. Scaffold `src/backtest/` package: `pyproject.toml`, README, empty modules.
2. `data.py` canonical schema + validators + `bars_to_canonical_bars()`. Test against synthetic fixtures.
3. `config.py`, `result.py`, `metrics.py`, and the canonical execution ledger. Import `Strategy`, `ExitRules`, `BarFrame` from `src/strategy/protocol.py` (prerequisite step 0a). Add hand-computed metric tests plus golden fill-ledger tests for long / flat / short transitions.
4. **Strategy causality validator.** Prefix-invariance tests prove that `generate_targets()` cannot read future rows unnoticed.
5. **VectorBT adapter** + `engine.run_backtest(strategy, bars, config, backend="vectorbt")`. `BuyAndHold` reference strategy. Smoke test: linear-ramp fixture, zero commission/slippage, fills match the golden ledger and total return matches by hand.
6. **Backtesting.py adapter.** Same `BuyAndHold` against linear ramp — must produce fills identical to the golden ledger and scalars identical to VectorBT to 1e-6 (cross-check sanity).
7. **Reconciler (scalar + fill count/timestamp).** Two-backend parity test on `BuyAndHold`. **Ship as PR #1 — demoable end-to-end with two engines.**
8. **Backtrader adapter.** Reconciler now triangulates. `SmaCrossover` reference strategy + within-tolerance parity test across all three.
9. **`ExitRules` plumbed end-to-end** on all three adapters after core parity is green. Stops / TPs / trailing / max-bars verified by quirk-regression tests against the conservative semantics above.
10. **Equity-curve pointwise reconciliation + fill-list / trade-list diff** in reconciler. CLI: `python -m sleep_trading_backtest.cli run <strategy.py> --data fixture.parquet --reconcile`.
11. **Quirk regression suite** (`test_quirk_regressions.py`) codifying known cross-framework gotchas. **Ship steps 8–11 as PR #2 — closes v1.**

Ship each step with tests before the next.

## v1 verification

Three layered checks under `pytest src/backtest/tests/`:

- **Sanity baseline — buy-and-hold parity.** Linear-ramp fixture, 1000 bars, zero commission/slippage. All backends must agree on total return to 1e-6, Sharpe to 1e-4, exactly 1 trade. **Any failure here is an adapter bug, not a strategy bug** — proves the harness before we trust it on real strategies.
- **SMA crossover within tolerance.** Sine-overlay fixture, ~10 target changes. Fill and trade counts must match exactly across backends; equity curves agree to ≤ 0.5% max pointwise relative deviation; total return ±50 bps.
- **Quirk regression suite** — strategies crafted to expose specific bug classes:
  - Prefix-invariance failure in `generate_targets()` is rejected as look-ahead leakage before any engine runs.
  - Target change on the very last bar must not produce a phantom fill.
  - All-NaN warmup region produces zero trades, no crash.
  - Flip from −1 to +1 in one bar closes + reverse-opens in one step.
  - A `0` target between two `1` targets exits to flat and later re-enters; `0` never means "hold."
  - Intrabar `stop_loss_pct=0.01` triggered follows the conservative exit semantics, including gap-through behavior.

Manual smoke after PR #1: `python -m sleep_trading_backtest.cli run strategies/buy_and_hold.py --data tests/fixtures/synthetic_ramp_1m.parquet --reconcile` prints a green diff table with two backends agreeing.

## v1 open questions

- **Tolerance defaults.** Are ±50 bps / Sharpe ±0.15 right for daily bars? Higher-frequency strategies need tighter thresholds; lower-frequency may need looser. Per-fixture override or one-size-fits-all in v1?
- **`raw_metrics` shape.** Backends emit wildly different native dicts. Standardize keys (lossy), pass through verbatim (debug-only), or both behind a flag?
- **AGPL on Backtesting.py.** Fine for personal research; if ever shipped as a hosted service, Backtesting.py needs to be optional. Worth a `--skip backtesting_py` CLI flag in v1, or defer?
- **Decimal vs float at the result boundary.** `equity_curve` is `float64` for engine compatibility, but canonical fills / derived trade P&L could be `Decimal` if round-tripped through the normalized schema. Worth the friction?

---

# v2

## v2 goal

Extend v1 along two axes without changing its contract: (a) add an event-driven `EventStrategy` ABC for path-dependent logic the target-series v1 API can't express, and (b) integrate the engine with the broader data layer — `src/data` `ReplayAdapter` / `DataClient` for shared historical reads, a walk-forward harness on top of the engine, and a parameter-sweep helper that delegates to VectorBT's vectorized form. v1 strategies keep running unchanged.

## v2 why

v1's target-series API trades expressiveness for cross-checking. That's the right v1 tradeoff. But strategies that condition on their own P&L, holding time, or fill price need an imperative event loop. v2 adds that surface in a way that preserves cross-checking where possible (Backtesting.py + Backtrader) and explicitly drops it where not (VectorBT).

Walk-forward and `ReplayAdapter` integration are independent of the API extension but bundled here as the natural next round of engine maturity: v1 proves the cross-check; v2 proves we can use it at research scale and at the live-vs-backtest seam.

## v2 design decisions

1. **`EventStrategy` is event-driven engines only.** Backtesting.py and Backtrader natively; VectorBT is skipped with a `requires_event_driven=True` warning. Cross-checking fidelity drops from three engines to two; reconciliation report flags this. `reconcile.run_all` on a v1 `Strategy` still runs all three.
2. **Reuse the v1 target vocabulary.** `EventStrategy` decides incrementally per bar, but it still expresses desired exposure (`-1 / 0 / +1`) rather than backend verbs like `buy` / `sell` / `close`. It returns the same `BacktestResult` schema. `ExitRules` remain valid as declarative defaults; `on_bar` can override them with an explicit request. `BacktestConfig`, `Tolerance`, the reconciler — unchanged.
3. **Walk-forward is a thin harness around `engine.run_backtest`.** Splits `CanonicalBars.frame` into train/test windows while preserving metadata, runs the engine on each, aggregates. Optimization (picking the best params on the train window) is opt-in via a `param_grid` argument.
4. **`ReplayAdapter` integration is a bridge, not a rewrite.** `engine.run_backtest` accepts `bars: CanonicalBars | AsyncIterator[Bar]` — when given the async iterator, it buffers Bars through `bars_to_canonical_bars()` and proceeds. Cross-check path stays frame-backed because that's what the engines expect internally.
5. **Parameter sweep delegates to VectorBT.** 1000 combinations through Backtrader is hours; VectorBT does it in seconds. The sweep helper runs all combinations on VectorBT, returns the top N by configurable metric, then optionally cross-checks the top N on Backtesting.py and Backtrader for fidelity validation. The "VectorBT for discovery, event-driven for validation" pattern from the survey.

## v2 unified API contract additions

The v1 contracts (`CanonicalBars`, `TargetSeries`, fill list, trade list, equity curve, `AdapterCapabilities`, error model) remain in force unchanged. v2 adds three new canonical types and one new contract on top.

### Position (canonical, read-only view)

```python
@dataclass(frozen=True)
class Position:
    side: Literal["long", "short", "flat"]
    size: Decimal                   # absolute quantity; Decimal("0") when flat
    entry_px: Decimal | None        # None when flat
    entry_ts: datetime | None       # None when flat; tz-aware UTC
    unrealized_pnl: Decimal         # mark-to-market against ctx.now's bar close; signed
```

### Fill (canonical, read-only event)

```python
@dataclass(frozen=True)
class Fill:
    ts: datetime                    # exchange ts of the fill (= the bar's open ts under next_open policy)
    side: Literal["buy", "sell"]
    size: Decimal                   # absolute, positive
    price: Decimal                  # actual fill including slippage
    commission: Decimal             # in account currency
    is_close: bool                  # True if this fill closed an existing position; False if it opened or scaled in
```

### EventStrategy contract

When `EventStrategy.on_bar(bar, ctx)` is called, the engine guarantees:

1. **Chronological order** — `bar.ts_open` strictly increases between calls; no out-of-order, no skipped bars, no repeated bars.
2. **Closed-bar visibility** — `bar.close` is known and final. No bar with `ts_open > ctx.now` exists in the strategy's view.
3. **Single call per bar** — exactly one `on_bar` invocation per strategy per bar.
4. **`ctx.now` matches `bar.ts_close`** — they are the same instant; the strategy can use either.
5. **No look-ahead** — the returned `TargetUpdate`, if any, fills at the NEXT bar's open (`next_open` policy, inherited from v1 config).

`on_fill(fill, ctx)` is called synchronously after the engine commits a fill, **before** the next `on_bar`. Fills always arrive in the same order across both event-driven adapters (Backtesting.py + Backtrader) for the same logical strategy — this is what makes EventStrategy cross-checkable.

`on_start(ctx)` is called once before the first bar; `on_end(ctx)` once after the last. Use these for setup / teardown only — they cannot place orders.

The `TargetUpdate` return value semantics:
- `None` — keep the current target; declarative `ExitRules` (if set on the strategy) remain active for this bar.
- `PositionTarget` (`-1`, `0`, `+1`) — request the same canonical short / flat / long exposure used by v1.
- `TargetRequest(...)` — request a canonical target plus explicit sizing or per-bar stop / take-profit overrides of `ExitRules`.

### EventStrategy adapter contract

Adapters with `capabilities.supports_event_driven is True` (v2: Backtesting.py, Backtrader; never VectorBT):

**MUST**
1. Construct `Context` fresh for each `on_bar` call with the engine's current `now`, `position`, `cash`, `equity`, `bars_seen`. The Context is read-only — the strategy cannot mutate engine state through it.
2. Translate the returned `TargetUpdate` to the same canonical transition model as v1 and defer the fill to the next bar's open.
3. Call `on_fill(fill, ctx)` after every engine-confirmed fill, before the next `on_bar`. The `Fill` is populated from the engine's fill report.
4. Honor declarative `ExitRules` on the strategy as defaults — `on_bar` returning `None` leaves any active stop / take-profit / trailing-stop / max-bars-held alive. A `TargetRequest` with stop/TP fields overrides them for the resulting position.

**MUST NOT**
1. Call `on_bar` more than once per (strategy, bar), or out of order, or skip a bar.
2. Translate an unknown `TargetUpdate` value silently — raise `UnsupportedFeatureError(target_update=...)`.
3. Mutate the `Context`, `Bar`, or `Fill` (all are frozen dataclasses; the contract codifies this).

### Reconciler behavior on EventStrategy

`reconcile.run_all(strategy, ...)` when `isinstance(strategy, EventStrategy)`:
- skips every adapter where `capabilities.supports_event_driven is False` (VectorBT)
- the `ReconciliationReport` includes `fidelity = "reduced"` and lists which adapters were skipped and why
- if fewer than 2 compatible adapters remain after skipping, raises `ReconciliationError("cross-check requires ≥2 compatible adapters; only {n} available")`. Cross-checking is the point; one engine is just a single backtest.

### Streaming-input contract (ReplayAdapter bridge)

`engine.run_backtest_streaming(strategy, bars: AsyncIterator[Bar], config, backend)`:

**MUST**
1. Consume the iterator to exhaustion before invoking the adapter. Buffering via `bars_to_canonical_bars(...)` is acceptable in v2; true streaming is v3.
2. Validate the assembled data against `CanonicalBars` rules — same validator as the synchronous path.
3. Surface iterator-side errors (`DataGapError`, etc., from `src/data`) as `ValidationError` with the original cause attached.

The returned `BacktestResult` is byte-identical to what `engine.run_backtest(strategy, canonical_bars, config, backend)` would return for the same data — this is the v2 verification target.

## v2 abstractions

### EventStrategy

```python
class EventStrategy(ABC):
    """Event-driven strategy with per-bar callbacks.

    Runs on event-driven engines (Backtesting.py, Backtrader). VectorBT is skipped
    with a warning in reconcile.run_all().
    """
    name: str
    warmup_bars: int = 0
    requires_event_driven: ClassVar[bool] = True

    def on_start(self, ctx: Context) -> None: ...
    @abstractmethod
    def on_bar(self, bar: Bar, ctx: Context) -> TargetUpdate | None: ...
    def on_fill(self, fill: Fill, ctx: Context) -> None: ...
    def on_end(self, ctx: Context) -> None: ...

@dataclass(frozen=True)
class Context:
    now: datetime
    position: Position                       # side, size, entry_px, entry_ts
    cash: Decimal
    equity: Decimal
    bars_seen: int

TargetUpdate = PositionTarget | TargetRequest

@dataclass(frozen=True)
class TargetRequest:
    target: PositionTarget
    target_size: Decimal | None = None       # None => full_notional
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
```

`Context` is the read-only window into engine state — same shape across both event-driven adapters so strategy code is portable. The target vocabulary stays the same as v1; only the delivery mode changes from vectorized batch output to per-bar callbacks.

### Walk-forward harness

```python
@dataclass(frozen=True)
class WalkForwardConfig:
    train_window: pd.Timedelta
    test_window: pd.Timedelta
    step: pd.Timedelta
    optimization_metric: str = "sharpe"
    param_grid: dict[str, list[Any]] | None = None      # None => no optimization

def walk_forward(
    strategy_cls: type[Strategy] | type[EventStrategy],
    bars: CanonicalBars,
    config: BacktestConfig,
    wf_config: WalkForwardConfig,
    backend: str = "vectorbt",
) -> WalkForwardReport: ...
```

`WalkForwardReport` aggregates per-window results: out-of-sample equity stitching, per-window metrics, parameter stability across windows, overall verdict (robust or overfit?).

### Parameter sweep

```python
def parameter_sweep(
    strategy_cls: type[Strategy],            # target-series; sweep on event-driven too slow
    bars: CanonicalBars,
    config: BacktestConfig,
    param_grid: dict[str, list[Any]],
    top_n: int = 10,
    metric: str = "sharpe",
    cross_check_top: bool = True,
) -> SweepReport: ...
```

Runs all combinations through VectorBT (vectorized), ranks by `metric`, then optionally cross-checks the top `top_n` on all three engines. Catches "VectorBT thinks this combo is great but Backtrader disagrees" — usually a slippage-application or look-ahead bug specific to one engine.

### ReplayAdapter bridge

```python
async def run_backtest_streaming(
    strategy: Strategy | EventStrategy,
    bars: AsyncIterator[Bar],
    config: BacktestConfig,
    backend: str,
) -> BacktestResult: ...
```

Internally buffers via `bars_to_canonical_bars()` (engines need the whole frame upfront). True bar-by-bar streaming is a v3 concern.

## v2 module layout (additions over v1)

```
src/backtest/
  sleep_trading_backtest/
    event_strategy.py                 # NEW: EventStrategy ABC, Context, TargetUpdate, TargetRequest
    walk_forward.py                   # NEW: walk_forward(), WalkForwardConfig, WalkForwardReport
    sweep.py                          # NEW: parameter_sweep(), SweepReport
    streaming.py                      # NEW: run_backtest_streaming() bridge to ReplayAdapter
    adapters/
      backtesting_py_adapter.py       # MODIFIED: handle EventStrategy
      backtrader_adapter.py           # MODIFIED: handle EventStrategy
      vectorbt_adapter.py             # MODIFIED: skip with warning if requires_event_driven
  tests/
    test_event_strategy_parity.py     # NEW
    test_walk_forward.py              # NEW
    test_parameter_sweep.py           # NEW
    test_streaming_bridge.py          # NEW
```

v1 modules (`config.py`, `result.py`, `data.py`, `metrics.py`, `reconcile.py`) unchanged. `Strategy` / `ExitRules` / `BarFrame` continue to be imported from `src/strategy/protocol.py`; v2 adds an `EventStrategy` ABC there too (event-driven companion to `Strategy`), and `src/backtest/event_strategy.py` becomes an adapter-side translation layer over that contract, not a new ABC owner.

## v2 execution order

Assumes v1 has shipped and `src/data/events.py` exists. Also assumes `src/data` `ReplayAdapter` has at least a Parquet implementation (per [`data.md`](./data.md) step 7) — if not, the streaming bridge stubs until ReplayAdapter lands.

1. **`EventStrategy` ABC, `Context`, `TargetUpdate`, `TargetRequest`.** Pure types, no engine glue yet.
2. **Backtesting.py adapter handles `EventStrategy`.** Translate `on_bar` → `next()` with `Context` constructed each bar. Translate target updates into the same canonical long / flat / short transitions as v1. Unit test: simple event strategy (e.g., "target long on RSI<30, flat on RSI>70") behaves correctly.
3. **Backtrader adapter handles `EventStrategy`.** Same translation pattern. **Ship as PR #3 — `EventStrategy` working on two event-driven engines, with parity test.**
4. **`reconcile.run_all` skips VectorBT on `EventStrategy` with clear warning.** Report explicitly notes "cross-check fidelity: 2 engines (VectorBT skipped — strategy is event-driven)".
5. **Walk-forward harness.** Splits `CanonicalBars.frame`, preserves metadata per window, runs `engine.run_backtest` per window, aggregates. Optional `param_grid` enables in-sample optimization. Test against synthetic fixture with known-stable and known-unstable parameter regimes.
6. **Parameter sweep.** Drives VectorBT vectorized; cross-checks top N if requested. **Ship walk-forward + sweep as PR #4.**
7. **`ReplayAdapter` streaming bridge.** Once `src/data` lands a working `ReplayAdapter`, wire `run_backtest_streaming(strategy, replay.events(), config, backend)`. Buffers via `bars_to_canonical_bars()`. **Ship as PR #5 — closes v2.**

## v2 verification

In addition to v1's verification suite:

- **EventStrategy parity.** Known-result event strategy on Backtesting.py and Backtrader must produce identical scalars to 1e-4 and the same trade list. Tighter than v1's tolerance because only two engines — no triangulation.
- **EventStrategy ↔ Strategy equivalence.** A target-position strategy and its equivalent event-driven rewrite ("emit target series" vs "return the same target per bar") must produce results within v1 tolerance on both event-driven engines. Catches bugs in the `EventStrategy` translation layer.
- **Walk-forward determinism.** Same bars, same strategy, same windows → identical aggregated metrics.
- **Walk-forward overfitting detection.** A deliberately-overfitted parameter ("buy when bar index mod 7 == 3") shows in-sample / out-of-sample divergence the report flags clearly.
- **Parameter sweep agreement.** Sweep on VectorBT, cross-check top N on the other two. Top N rankings must agree at the qualitative level. Catches engine-specific overfitting.
- **Streaming bridge.** Same Parquet file, read as `CanonicalBars` vs read as `AsyncIterator[Bar]` through `ReplayAdapter` → byte-identical canonical frame + metadata at the engine boundary.

## v2 open questions

- **EventStrategy on VectorBT.** Slow-loop fallback (events translated to a bar-by-bar Python loop wrapping VectorBT's target path) with a fidelity warning, or strictly skip? Slow-loop preserves three-engine cross-check; strict skip is honest about what's tested.
- **Walk-forward parallelism.** Each window is independent — easy to parallelize. Multiprocessing? Joblib? Or keep sequential in v2 for determinism, parallelize in v3?
- **Sweep metric extensibility.** Hardcoded options (`"sharpe" | "calmar" | "total_return"`) or accept a callable `metric: Callable[[BacktestResult], float]`?
- **Streaming bridge realtime-ness.** v2 ships buffer-then-run. A true streaming backtest (engine consumes bars as they arrive, useful for paper-trading-like simulation) is a v3 concern.
- **EventStrategy translation correctness.** The hardest v2 risk: `on_bar` → engine-native translation must produce the same fills across Backtesting.py and Backtrader for the same logical strategy. Quirk regression suite needs to grow specifically for EventStrategy quirks.

---

## Out of scope (this plan, both versions)

- Live execution / OMS — separate component, not yet planned.
- Strategy / features / risk engine abstractions — separate component, not yet planned.
- Multi-asset / portfolio backtests — possible v3, not v1 or v2.
- Nautilus, QuantConnect LEAN, Zipline-Reloaded adapters — possible v3, gated on a real need.
- Borrow / margin / financing fee modeling.
- Tick-level backtesting — bars only; tick-level cross-check across these three engines is materially harder and a separate plan if ever pursued.
