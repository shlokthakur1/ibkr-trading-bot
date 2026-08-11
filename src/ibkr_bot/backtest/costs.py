"""ASX cost/slippage model — concrete, reasoned defaults (plan §2.4).

Round-trip cost estimate at the defaults below: ~2 x (8bps commission + 10bps slippage) = ~36bps
per round trip, in line with typical published estimates for ASX large-cap active trading. These
are *stated assumptions*, not measurements — recalibrate against real paper-trading fills once
they exist (see plan's risk #9).
"""

from __future__ import annotations

from dataclasses import dataclass

# ASX tick table: the minimum price increment a fill can legally sit on.
_TICK_BANDS = (
    (0.10, 0.001),
    (2.00, 0.005),
    (float("inf"), 0.01),
)


def tick_size(price: float) -> float:
    """The ASX tick size applicable at `price`."""
    for upper_bound, size in _TICK_BANDS:
        if price < upper_bound:
            return size
    return _TICK_BANDS[-1][1]


def round_to_tick(price: float) -> float:
    """Round `price` to the nearest valid ASX tick — a fill can't sit at an intra-band price."""
    size = tick_size(price)
    return round(round(price / size) * size, 10)  # 10dp guards against float rounding noise


@dataclass(frozen=True)
class CostModel:
    """Commission + slippage assumptions, applied consistently to every simulated fill."""

    commission_pct: float = 0.0008  # 8 bps
    commission_min_aud: float = 6.0
    slippage_bps: float = 0.0010  # 10 bps, always adverse

    def commission(self, notional: float) -> float:
        return max(abs(notional) * self.commission_pct, self.commission_min_aud)

    def entry_fill_price(self, reference_open: float) -> float:
        """Market-order entry at next-bar-open, slipping adverse (up, since we're buying)."""
        return round_to_tick(reference_open * (1 + self.slippage_bps))

    def stop_fill_price(self, stop_price: float) -> float:
        """Stop-loss exit: a stop order that becomes a market order once triggered, can slip
        further adverse (down, since we're selling to exit a long)."""
        return round_to_tick(stop_price * (1 - self.slippage_bps))

    def target_fill_price(self, target_price: float) -> float:
        """Take-profit exit: a resting limit order — no adverse slippage by construction."""
        return round_to_tick(target_price)

    def market_exit_fill_price(self, reference_open: float) -> float:
        """Time-stop (or any other market-order) exit at next-bar-open, slipping adverse."""
        return round_to_tick(reference_open * (1 - self.slippage_bps))
