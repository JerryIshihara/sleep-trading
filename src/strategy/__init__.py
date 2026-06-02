"""Strategy contract + authoring.

Public surface — what downstream consumers (e.g. ``src/backtesting/``) import.
"""

from strategy.protocol import (
    BarFrame,
    ExitRules,
    PositionTarget,
    Strategy,
)

__all__ = [
    "BarFrame",
    "ExitRules",
    "PositionTarget",
    "Strategy",
]
