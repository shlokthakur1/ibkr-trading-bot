"""Cash/position ledger for the backtest engine, plus deterministic entry-slot allocation.

This owns the *only* mutable state in the backtest: cash, currently open positions, and the
list of closed trades. Everything else (indicator computation, entry decisions, cost/fill
pricing) is a pure function called from here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from ibkr_bot.strategy.types import ExitReason, TargetPosition


@dataclass
class OpenPosition:
    symbol: str
    entry_date: date
    entry_price: float
    quantity: int
    stop_price: float
    target_price: float
    time_stop_bars: int
    bars_held: int
    z_score_at_entry: float
    rsi_at_entry: float
    strategy_id: str
    config_hash: str


@dataclass(frozen=True)
class ClosedTrade:
    symbol: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    exit_reason: str
    quantity: int
    gross_pnl: float
    costs: float
    net_pnl: float
    r_multiple: float
    bars_held: int
    z_score_at_entry: float
    rsi_at_entry: float


def rank_and_trim(candidates: list[TargetPosition], free_slots: int) -> list[TargetPosition]:
    """Deterministic tie-break when more entry candidates fire than there are free portfolio
    slots: most-oversold z-score first, then alphabetical symbol (plan §2.2). Candidates not
    admitted are dropped, not carried forward — by the next bar the market has moved and the
    original conditions may no longer hold; a documented v1 simplification.
    """
    if free_slots <= 0:
        return []
    ranked = sorted(candidates, key=lambda c: (c.z_score, c.symbol))
    return ranked[:free_slots]


class Portfolio:
    def __init__(self, initial_equity: float, cost_model):
        self.cash = initial_equity
        self.cost_model = cost_model
        self.open_positions: dict[str, OpenPosition] = {}
        self.closed_trades: list[ClosedTrade] = []

    def equity(self, mark_prices: dict[str, float]) -> float:
        positions_value = sum(
            pos.quantity * mark_prices[sym]
            for sym, pos in self.open_positions.items()
            if sym in mark_prices
        )
        return self.cash + positions_value

    def open_position(
        self, target: TargetPosition, fill_price: float, fill_date: date, equity_at_fill: float
    ) -> bool:
        """Attempt to open a position sized at `target.target_weight` of `equity_at_fill`.
        Returns False (no-op) if the resulting share quantity would be zero.
        """
        notional = equity_at_fill * target.target_weight
        quantity = math.floor(notional / fill_price)
        if quantity < 1:
            return False

        commission = self.cost_model.commission(quantity * fill_price)
        self.cash -= quantity * fill_price + commission
        self.open_positions[target.symbol] = OpenPosition(
            symbol=target.symbol,
            entry_date=fill_date,
            entry_price=fill_price,
            quantity=quantity,
            stop_price=fill_price * (1 - target.stop_loss_pct),
            target_price=fill_price * (1 + target.take_profit_pct),
            time_stop_bars=target.time_stop_bars,
            bars_held=0,
            z_score_at_entry=target.z_score,
            rsi_at_entry=target.rsi,
            strategy_id=target.strategy_id,
            config_hash=target.config_hash,
        )
        return True

    def close_position(
        self, symbol: str, fill_price: float, fill_date: date, reason: ExitReason
    ) -> ClosedTrade:
        pos = self.open_positions.pop(symbol)
        commission = self.cost_model.commission(pos.quantity * fill_price)
        entry_commission = self.cost_model.commission(pos.quantity * pos.entry_price)
        gross_pnl = (fill_price - pos.entry_price) * pos.quantity
        total_costs = commission + entry_commission
        net_pnl = gross_pnl - total_costs
        risk_amount = (pos.entry_price - pos.stop_price) * pos.quantity
        r_multiple = net_pnl / risk_amount if risk_amount > 0 else float("nan")

        self.cash += pos.quantity * fill_price - commission

        trade = ClosedTrade(
            symbol=symbol,
            entry_date=pos.entry_date,
            entry_price=pos.entry_price,
            exit_date=fill_date,
            exit_price=fill_price,
            exit_reason=reason.value,
            quantity=pos.quantity,
            gross_pnl=gross_pnl,
            costs=total_costs,
            net_pnl=net_pnl,
            r_multiple=r_multiple,
            bars_held=pos.bars_held,
            z_score_at_entry=pos.z_score_at_entry,
            rsi_at_entry=pos.rsi_at_entry,
        )
        self.closed_trades.append(trade)
        return trade
