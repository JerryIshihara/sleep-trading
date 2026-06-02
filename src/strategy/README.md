# Strategy

Strategy contract and authoring. Owns the `Strategy` ABC, `ExitRules`,
`PositionTarget`, and the `BarFrame` Protocol that consumers (notably
`src/backtesting/`) depend on.

**Dependency rule:** this package never imports from `src/backtesting/`.
Strategies must remain authorable and unit-testable without the backtest
package installed.

See [`../../docs/plan/backtesting.md`](../../docs/plan/backtesting.md) — the
"Strategy module ↔ backtest module seam" section pins the contract.
