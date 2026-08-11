"""Same-bar TP/SL touch detection — the "did this bar's range hit my exit levels" question.

Ported mechanics from the earlier prototype's equity_backtest.py: high/low-range detection,
with the conservative "stop wins on a same-bar tie" assumption (OHLC bars alone can't reveal
the true intrabar path, so when both levels are touched in the same bar we can't tell which was
hit first — assuming the worse outcome is the safer bias for a backtest).
"""

from __future__ import annotations

from ibkr_bot.strategy.types import ExitReason


def detect_intrabar_exit(
    bar_high: float, bar_low: float, stop_price: float, target_price: float
) -> ExitReason | None:
    """Return which exit (if any) this bar's high/low range would have triggered."""
    hit_stop = bar_low <= stop_price
    hit_target = bar_high >= target_price
    if hit_stop:
        return ExitReason.STOP_LOSS  # stop wins ties, and is checked first regardless
    if hit_target:
        return ExitReason.TAKE_PROFIT
    return None
