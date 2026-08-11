from datetime import date

import pytest

from ibkr_bot.backtest.costs import CostModel
from ibkr_bot.backtest.portfolio import Portfolio, rank_and_trim
from ibkr_bot.strategy.types import ExitReason, TargetPosition


def _target(symbol: str, z_score: float, target_weight: float = 0.10) -> TargetPosition:
    return TargetPosition(
        symbol=symbol,
        as_of_date=date(2020, 1, 1),
        side="LONG",
        target_weight=target_weight,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        time_stop_bars=5,
        reason="entry: dip+uptrend+rsi",
        strategy_id="test",
        config_hash="sha256:test",
        z_score=z_score,
        rsi=35.0,
    )


def test_rank_and_trim_orders_by_most_oversold_zscore_then_symbol():
    candidates = [
        _target("BHP", z_score=-1.5),
        _target("CBA", z_score=-2.5),
        _target("WES", z_score=-2.5),
    ]
    ranked = rank_and_trim(candidates, free_slots=10)
    assert [c.symbol for c in ranked] == ["CBA", "WES", "BHP"]


def test_rank_and_trim_respects_free_slots():
    candidates = [_target("A", -3.0), _target("B", -2.0), _target("C", -1.0)]
    assert [c.symbol for c in rank_and_trim(candidates, free_slots=2)] == ["A", "B"]


def test_rank_and_trim_zero_slots_returns_empty():
    candidates = [_target("A", -3.0)]
    assert rank_and_trim(candidates, free_slots=0) == []
    assert rank_and_trim(candidates, free_slots=-1) == []


def test_open_position_sizes_by_target_weight_and_floors_quantity():
    portfolio = Portfolio(initial_equity=100_000.0, cost_model=CostModel())
    target = _target("CBA", z_score=-2.0, target_weight=0.10)
    opened = portfolio.open_position(
        target, fill_price=100.0, fill_date=date(2020, 1, 2), equity_at_fill=100_000.0
    )
    assert opened is True
    pos = portfolio.open_positions["CBA"]
    assert pos.quantity == 100  # floor(10_000 / 100.0)
    assert pos.stop_price == pytest.approx(95.0)
    assert pos.target_price == pytest.approx(110.0)
    # cash reduced by notional + commission
    commission = CostModel().commission(100 * 100.0)
    assert portfolio.cash == pytest.approx(100_000.0 - 100 * 100.0 - commission)


def test_open_position_rejects_too_small_a_notional():
    portfolio = Portfolio(initial_equity=1_000.0, cost_model=CostModel())
    target = _target("CBA", z_score=-2.0, target_weight=0.001)  # tiny notional
    opened = portfolio.open_position(
        target, fill_price=100.0, fill_date=date(2020, 1, 2), equity_at_fill=1_000.0
    )
    assert opened is False
    assert "CBA" not in portfolio.open_positions
    assert portfolio.cash == 1_000.0  # untouched


def test_close_position_computes_pnl_and_r_multiple():
    portfolio = Portfolio(initial_equity=100_000.0, cost_model=CostModel())
    target = _target("CBA", z_score=-2.0, target_weight=0.10)
    portfolio.open_position(
        target, fill_price=100.0, fill_date=date(2020, 1, 2), equity_at_fill=100_000.0
    )
    trade = portfolio.close_position(
        "CBA", fill_price=110.0, fill_date=date(2020, 1, 10), reason=ExitReason.TAKE_PROFIT
    )
    assert trade.quantity == 100
    assert trade.gross_pnl == pytest.approx((110.0 - 100.0) * 100)
    assert trade.net_pnl < trade.gross_pnl  # costs deducted
    # risk = (entry - stop) * qty = (100 - 95) * 100 = 500
    assert trade.r_multiple == pytest.approx(trade.net_pnl / 500.0)
    assert "CBA" not in portfolio.open_positions
    assert portfolio.closed_trades == [trade]
