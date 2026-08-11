"""Backtest performance metrics — pure functions of an equity curve and a trade list."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .portfolio import ClosedTrade

TRADING_DAYS_PER_YEAR = 252


def return_stats(equity_curve: pd.Series) -> tuple[float, float]:
    """(total_return_pct, cagr_pct) for any equity-like series — shared by the strategy's own
    metrics and by benchmark comparison (benchmark.py) so the CAGR formula lives in one place.
    """
    num_days = len(equity_curve)
    period_years = max(num_days - 1, 1) / TRADING_DAYS_PER_YEAR
    initial = float(equity_curve.iloc[0])
    final = float(equity_curve.iloc[-1])
    total_return_pct = (final / initial - 1.0) * 100.0
    cagr_pct = (
        ((final / initial) ** (1.0 / period_years) - 1.0) * 100.0
        if period_years > 0 and initial > 0
        else float("nan")
    )
    return total_return_pct, cagr_pct


def compute_metrics(
    equity_curve: pd.Series,
    trades: list[ClosedTrade],
    max_concurrent_positions: int,
    positions_open: pd.Series | None = None,
    risk_free_rate: float = 0.0,
) -> dict:
    """`equity_curve` is a Series of daily equity values indexed by date, oldest first."""
    daily_returns = equity_curve.pct_change().dropna()
    total_return_pct, cagr_pct = return_stats(equity_curve)

    daily_std = daily_returns.std(ddof=0)
    annualized_vol_pct = float(daily_std * math.sqrt(TRADING_DAYS_PER_YEAR) * 100.0)
    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = daily_returns - rf_daily
    sharpe = (
        float(excess.mean() / daily_std * math.sqrt(TRADING_DAYS_PER_YEAR))
        if daily_std > 0
        else float("nan")
    )

    downside = daily_returns[daily_returns < 0]
    downside_std = downside.std(ddof=0)
    sortino = (
        float(excess.mean() / downside_std * math.sqrt(TRADING_DAYS_PER_YEAR))
        if downside_std > 0
        else float("nan")
    )

    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    max_drawdown_pct = float(drawdown.min() * 100.0)

    num_trades = len(trades)
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl < 0]
    win_rate_pct = (len(wins) / num_trades * 100.0) if num_trades else float("nan")
    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = abs(sum(t.net_pnl for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("nan")
    r_multiples = [t.r_multiple for t in trades if not math.isnan(t.r_multiple)]
    avg_r_multiple = float(np.mean(r_multiples)) if r_multiples else float("nan")

    exposure_pct = (
        float(positions_open.mean() / max_concurrent_positions * 100.0)
        if positions_open is not None and max_concurrent_positions > 0
        else float("nan")
    )

    return {
        "total_return_pct": total_return_pct,
        "cagr_pct": cagr_pct,
        "annualized_vol_pct": annualized_vol_pct,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown_pct": max_drawdown_pct,
        "win_rate_pct": win_rate_pct,
        "profit_factor": profit_factor,
        "avg_r_multiple": avg_r_multiple,
        "num_trades": num_trades,
        "exposure_pct": exposure_pct,
    }
