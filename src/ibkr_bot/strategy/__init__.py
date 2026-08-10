"""Deterministic, config-driven strategy engine (ASX large-cap "buy the dip in an uptrend", v1).

Pure functions of an OHLCV panel — no I/O, no wall-clock reads, no broker/asyncio imports. This
is what lets the same strategy code run unmodified across backtest, paper, and live modes; see
the architecture plan §2.2/§2.6.
"""

from .config import StrategyConfig, config_hash, load_config
from .engine import StrategyEngine
from .types import ExitReason, TargetPosition

__all__ = [
    "StrategyConfig",
    "load_config",
    "config_hash",
    "StrategyEngine",
    "TargetPosition",
    "ExitReason",
]
