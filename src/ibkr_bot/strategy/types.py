"""The strategy engine's only public output type: TargetPosition.

This is the abstract boundary described in the architecture plan (§2.2/§2.6): the strategy
engine emits these, and a mode-specific ExecutionContext (built in later phases) is the only
thing that decides whether a TargetPosition becomes a simulated fill, a paper order, or a real
IBKR order. Nothing here import a broker or knows what mode it's running in.

v1 is long-only and entry-only: the strategy decides *when to enter* and attaches the exit
parameters (stop/target/time-stop) to the entry; actual exit *timing* is detected/enforced by
the executor (real bracket orders in paper/live, simulated OHLC-touch detection in backtest),
not re-decided by the strategy bar-by-bar.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Literal


class ExitReason(str, Enum):
    """Why a position was closed. Used by the executor/backtest engine, not emitted by the
    strategy itself (v1 never signals an exit — see module docstring)."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIME_STOP = "time_stop"


@dataclass(frozen=True)
class TargetPosition:
    """A single deterministic entry decision, with everything an executor needs to size,
    protect, and eventually time-stop the resulting position — but no fill price (unknown to
    the strategy) and no absolute stop/target price (computed by the executor once the actual
    fill price is known).
    """

    symbol: str
    as_of_date: date
    side: Literal["LONG"]
    target_weight: float
    stop_loss_pct: float
    take_profit_pct: float
    time_stop_bars: int
    reason: str
    strategy_id: str
    config_hash: str
    z_score: float
    rsi: float
