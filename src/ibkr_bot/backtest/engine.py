"""BacktestEngine: deterministic multi-symbol simulation over the strategy engine's decisions.

Sequencing per bar `i` (all times exchange-local, all symbols assumed to share one calendar):

  1. Execute any pending time-stop exits at today's open (scheduled by yesterday's bar).
  2. Admit pending entry candidates (signaled off yesterday's close) at today's open, subject to
     available portfolio slots — deterministic tie-break via `portfolio.rank_and_trim`.
  3. Check every open position's stop-loss/take-profit against today's high/low range; a
     position that neither exits nor breaches its time-stop bar count just gets bars_held += 1.
  4. Evaluate new entry signals off today's close (via StrategyEngine.decide) for symbols not
     currently in or pending a position; queue any as tomorrow's pending entries.
  5. Record today's mark-to-market equity.

Any position still open when the data ends is force-closed at the final close (a backtest
liquidation, not a strategy decision — documented so it isn't mistaken for a real exit signal).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ibkr_bot.strategy import StrategyConfig, StrategyEngine, config_hash
from ibkr_bot.strategy.types import ExitReason

from .costs import CostModel
from .fills import detect_intrabar_exit
from .metrics import compute_metrics
from .portfolio import ClosedTrade, Portfolio, rank_and_trim


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame  # columns: equity, cash, positions_open
    trades: list[ClosedTrade]
    metrics: dict
    config_hash: str
    symbols: list[str]
    initial_equity: float
    final_equity: float


class BacktestEngine:
    def __init__(
        self,
        strategy_config: StrategyConfig,
        cost_model: CostModel | None = None,
        initial_equity: float = 100_000.0,
    ):
        self.strategy_config = strategy_config
        self.cost_model = cost_model or CostModel()
        self.initial_equity = initial_equity

    def run(self, panels: dict[str, pd.DataFrame]) -> BacktestResult:
        symbols = sorted(panels)
        if not symbols:
            raise ValueError("panels must contain at least one symbol")

        reference_index = panels[symbols[0]].index
        for sym in symbols:
            if not panels[sym].index.equals(reference_index):
                raise ValueError(
                    f"panel for {sym!r} has a different date index than {symbols[0]!r} — "
                    "all symbols must share one calendar"
                )

        engines = {sym: StrategyEngine(self.strategy_config) for sym in symbols}
        prepared = {sym: engines[sym].prepare(panels[sym]) for sym in symbols}
        cfg_hash = config_hash(self.strategy_config)

        portfolio = Portfolio(self.initial_equity, self.cost_model)
        pending_entries: list = []
        pending_time_stop_exits: list[str] = []

        equity_rows = []

        n = len(reference_index)
        for i in range(n):
            today = reference_index[i]
            today_open = {sym: float(prepared[sym]["open"].iloc[i]) for sym in symbols}
            today_high = {sym: float(prepared[sym]["high"].iloc[i]) for sym in symbols}
            today_low = {sym: float(prepared[sym]["low"].iloc[i]) for sym in symbols}
            today_close = {sym: float(prepared[sym]["close"].iloc[i]) for sym in symbols}
            as_of_date = today.date() if hasattr(today, "date") else today

            # 1. Pending time-stop exits, at today's open.
            for sym in pending_time_stop_exits:
                if sym not in portfolio.open_positions:
                    continue  # defensive: shouldn't happen, but never double-close
                fill_price = self.cost_model.market_exit_fill_price(today_open[sym])
                portfolio.close_position(sym, fill_price, as_of_date, ExitReason.TIME_STOP)
            pending_time_stop_exits = []

            # 2. Admit pending entries at today's open.
            free_slots = self.strategy_config.max_concurrent_positions - len(
                portfolio.open_positions
            )
            admitted = rank_and_trim(pending_entries, free_slots)
            for target in admitted:
                fill_price = self.cost_model.entry_fill_price(today_open[target.symbol])
                equity_now = portfolio.equity(today_open)
                portfolio.open_position(target, fill_price, as_of_date, equity_now)
            pending_entries = []

            # 3. Check exits for currently open positions using today's high/low.
            for sym in list(portfolio.open_positions):
                pos = portfolio.open_positions[sym]
                reason = detect_intrabar_exit(
                    today_high[sym], today_low[sym], pos.stop_price, pos.target_price
                )
                if reason is ExitReason.STOP_LOSS:
                    fill_price = self.cost_model.stop_fill_price(pos.stop_price)
                    portfolio.close_position(sym, fill_price, as_of_date, reason)
                elif reason is ExitReason.TAKE_PROFIT:
                    fill_price = self.cost_model.target_fill_price(pos.target_price)
                    portfolio.close_position(sym, fill_price, as_of_date, reason)
                else:
                    pos.bars_held += 1
                    if pos.bars_held >= pos.time_stop_bars:
                        pending_time_stop_exits.append(sym)

            # 4. Evaluate new entry signals off today's close.
            pending_symbols = {t.symbol for t in pending_entries}
            for sym in symbols:
                if sym in portfolio.open_positions or sym in pending_symbols:
                    continue
                decision = engines[sym].decide(
                    prepared[sym], i, in_position=False, symbol=sym
                )
                if decision is not None:
                    pending_entries.append(decision)

            # 5. Mark-to-market equity snapshot.
            equity_today = portfolio.equity(today_close)
            equity_rows.append(
                {
                    "date": today,
                    "equity": equity_today,
                    "cash": portfolio.cash,
                    "positions_open": len(portfolio.open_positions),
                }
            )

        # Force-close anything still open at the end of the data (a backtest liquidation for
        # measurement purposes, not a strategy decision — at the final close, no extra slippage,
        # but normal commission still applies via close_position()).
        final_date = reference_index[-1]
        final_as_of = final_date.date() if hasattr(final_date, "date") else final_date
        final_close = {sym: float(prepared[sym]["close"].iloc[-1]) for sym in symbols}
        force_closed_any = False
        for sym in list(portfolio.open_positions):
            portfolio.close_position(sym, final_close[sym], final_as_of, ExitReason.TIME_STOP)
            force_closed_any = True
        if force_closed_any and equity_rows:
            equity_rows[-1]["equity"] = portfolio.equity({})
            equity_rows[-1]["cash"] = portfolio.cash
            equity_rows[-1]["positions_open"] = 0

        equity_curve = pd.DataFrame(equity_rows).set_index("date")
        metrics = compute_metrics(
            equity_curve["equity"],
            portfolio.closed_trades,
            self.strategy_config.max_concurrent_positions,
            positions_open=equity_curve["positions_open"],
        )

        return BacktestResult(
            equity_curve=equity_curve,
            trades=portfolio.closed_trades,
            metrics=metrics,
            config_hash=cfg_hash,
            symbols=symbols,
            initial_equity=self.initial_equity,
            final_equity=float(equity_curve["equity"].iloc[-1]),
        )
