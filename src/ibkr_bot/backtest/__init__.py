"""Deterministic backtest engine: cost model, fill simulation, portfolio ledger, metrics.

Consumes the strategy engine's TargetPosition stream (see ibkr_bot.strategy) and simulates
realistic ASX fills — see engine.py's module docstring for the exact per-bar sequencing.
"""

from .benchmark import benchmark_comparison, rebase_to_equity
from .costs import CostModel, round_to_tick, tick_size
from .engine import BacktestEngine, BacktestResult
from .metrics import compute_metrics, return_stats
from .portfolio import ClosedTrade, OpenPosition, Portfolio, rank_and_trim

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "CostModel",
    "tick_size",
    "round_to_tick",
    "compute_metrics",
    "return_stats",
    "benchmark_comparison",
    "rebase_to_equity",
    "Portfolio",
    "OpenPosition",
    "ClosedTrade",
    "rank_and_trim",
]
