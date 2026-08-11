import math
from datetime import date

import pandas as pd
import pytest

from ibkr_bot.backtest.metrics import compute_metrics
from ibkr_bot.backtest.portfolio import ClosedTrade


def _trade(net_pnl: float, r_multiple: float = 1.0) -> ClosedTrade:
    return ClosedTrade(
        symbol="TEST",
        entry_date=date(2020, 1, 1),
        entry_price=100.0,
        exit_date=date(2020, 1, 10),
        exit_price=110.0,
        exit_reason="take_profit",
        quantity=10,
        gross_pnl=net_pnl,
        costs=0.0,
        net_pnl=net_pnl,
        r_multiple=r_multiple,
        bars_held=5,
        z_score_at_entry=-2.0,
        rsi_at_entry=35.0,
    )


def _equity_series(values: list[float]) -> pd.Series:
    index = pd.date_range("2020-01-01", periods=len(values), freq="B")
    return pd.Series(values, index=index)


def test_flat_equity_curve_has_zero_drawdown_and_nan_sharpe():
    equity = _equity_series([100_000.0] * 10)
    metrics = compute_metrics(equity, trades=[], max_concurrent_positions=5)
    assert metrics["max_drawdown_pct"] == pytest.approx(0.0)
    assert math.isnan(metrics["sharpe"])  # zero variance -> undefined
    assert metrics["num_trades"] == 0
    assert math.isnan(metrics["win_rate_pct"])
    assert math.isnan(metrics["profit_factor"])


def test_monotonic_rise_has_no_drawdown_and_positive_cagr():
    equity = _equity_series([100_000.0 * (1.001**i) for i in range(300)])
    metrics = compute_metrics(equity, trades=[], max_concurrent_positions=5)
    assert metrics["max_drawdown_pct"] == pytest.approx(0.0, abs=1e-9)
    assert metrics["cagr_pct"] > 0
    assert metrics["total_return_pct"] > 0


def test_drawdown_detected_after_a_dip():
    equity = _equity_series([100.0, 110.0, 90.0, 95.0, 120.0])
    metrics = compute_metrics(equity, trades=[], max_concurrent_positions=5)
    # peak 110 -> trough 90 => -18.18%
    assert metrics["max_drawdown_pct"] == pytest.approx((90.0 / 110.0 - 1.0) * 100.0)


def test_win_rate_and_profit_factor_from_trades():
    trades = [_trade(100.0), _trade(50.0), _trade(-60.0)]
    equity = _equity_series([100_000.0, 100_090.0, 100_040.0])
    metrics = compute_metrics(equity, trades=trades, max_concurrent_positions=5)
    assert metrics["num_trades"] == 3
    assert metrics["win_rate_pct"] == pytest.approx(2 / 3 * 100.0)
    assert metrics["profit_factor"] == pytest.approx(150.0 / 60.0)
    assert metrics["avg_r_multiple"] == pytest.approx(1.0)


def test_profit_factor_is_nan_with_no_losses():
    trades = [_trade(100.0), _trade(50.0)]
    equity = _equity_series([100_000.0, 100_150.0])
    metrics = compute_metrics(equity, trades=trades, max_concurrent_positions=5)
    assert math.isnan(metrics["profit_factor"])


def test_exposure_pct_uses_positions_open_series():
    equity = _equity_series([100.0, 101.0, 102.0])
    positions_open = pd.Series([0, 2, 4], index=equity.index)
    metrics = compute_metrics(
        equity, trades=[], max_concurrent_positions=4, positions_open=positions_open
    )
    # mean(0,2,4)=2, /4 max = 50%
    assert metrics["exposure_pct"] == pytest.approx(50.0)
