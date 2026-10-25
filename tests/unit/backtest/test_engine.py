"""BacktestEngine end-to-end tests: a golden single-symbol trade, portfolio slot tie-breaking,
input validation, and repeat-run determinism (plan §Verification for Phase 3).
"""

from __future__ import annotations

import dataclasses
import math

import pandas as pd
import pytest

from ibkr_bot.backtest.costs import CostModel
from ibkr_bot.backtest.engine import BacktestEngine


def test_golden_single_symbol_trade(small_config, ohlcv_factory, dip_closes_factory):
    """A crafted uptrend+dip scenario produces exactly one trade with known characteristics.
    Values below were captured from a verified run of the engine and pinned as a golden check —
    any change to fill/cost mechanics that isn't intentional will break this.
    """
    df = ohlcv_factory(dip_closes_factory(tail_bars=9))
    engine = BacktestEngine(small_config, CostModel(), initial_equity=100_000.0)
    result = engine.run({"TEST": df})

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.symbol == "TEST"
    assert trade.entry_date.isoformat() == "2020-02-18"  # next-bar-open after the 02-17 signal
    assert trade.exit_reason == "time_stop"
    assert trade.bars_held == small_config.time_stop_bars
    assert trade.quantity == 82
    assert trade.entry_price == pytest.approx(121.62, abs=0.01)
    assert trade.net_pnl == pytest.approx(169.22, abs=0.5)
    assert trade.r_multiple == pytest.approx(0.339, abs=0.01)
    assert result.final_equity == pytest.approx(100_169.22, abs=0.5)
    assert result.metrics["num_trades"] == 1
    assert result.metrics["win_rate_pct"] == pytest.approx(100.0)


def test_signal_on_final_bar_surfaces_as_pending_not_silently_dropped(
    small_config, ohlcv_factory, dip_closes_factory
):
    """A real, useful case: data ends exactly on the bar an entry signal fires. There's no
    next-bar-open to fill it at, so it can never become a trade in this run — but it must show
    up in `pending_entries_at_end`, not vanish silently (this is exactly what a paper/live run
    picks up and fills at the next session's open).
    """
    closes = dip_closes_factory(tail_bars=9)
    entry_bar_index = 33  # the crafted scenario's known entry bar (2020-02-17), see conftest
    truncated_closes = closes[: entry_bar_index + 1]
    df = ohlcv_factory(truncated_closes)

    result = BacktestEngine(small_config, CostModel()).run({"TEST": df})

    assert result.trades == []
    assert len(result.pending_entries_at_end) == 1
    pending = result.pending_entries_at_end[0]
    assert pending.symbol == "TEST"
    assert pending.side == "LONG"


def test_no_entries_produces_flat_equity_curve_and_no_trades(small_config, ohlcv_factory):
    """A pure, unbroken uptrend never dips -> entry condition never fires -> no trades, and
    equity never moves (nothing was ever bought).
    """
    closes = [100.0 + i * 1.0 for i in range(60)]
    df = ohlcv_factory(closes)
    engine = BacktestEngine(small_config, CostModel(), initial_equity=100_000.0)
    result = engine.run({"TEST": df})

    assert result.trades == []
    assert (result.equity_curve["equity"] == 100_000.0).all()


def test_portfolio_slot_limit_ties_break_alphabetically(
    small_config, ohlcv_factory, dip_closes_factory
):
    """Two symbols with identical price paths signal on the same day; with only one free slot,
    the alphabetically-first symbol is admitted and the other's signal is dropped.
    """
    single_slot_config = dataclasses.replace(small_config, max_concurrent_positions=1)
    closes = dip_closes_factory(tail_bars=9)
    panels = {"AAA": ohlcv_factory(closes), "BBB": ohlcv_factory(closes)}
    engine = BacktestEngine(single_slot_config, CostModel(), initial_equity=100_000.0)
    result = engine.run(panels)

    traded_symbols = {t.symbol for t in result.trades}
    assert traded_symbols == {"AAA"}


def test_run_rejects_empty_panels(small_config):
    engine = BacktestEngine(small_config)
    with pytest.raises(ValueError, match="at least one symbol"):
        engine.run({})


def test_run_rejects_mismatched_calendars(small_config, ohlcv_factory, dip_closes_factory):
    closes = dip_closes_factory()
    df_a = ohlcv_factory(closes)
    df_b = ohlcv_factory(closes).iloc[1:]  # different index
    engine = BacktestEngine(small_config)
    with pytest.raises(ValueError, match="different date index"):
        engine.run({"AAA": df_a, "BBB": df_b})


def test_benchmark_comparison_added_when_benchmark_prices_given(
    small_config, ohlcv_factory, dip_closes_factory
):
    df = ohlcv_factory(dip_closes_factory(tail_bars=9))
    benchmark_prices = pd.Series(
        [100.0 * (1.0002**i) for i in range(len(df))], index=df.index
    )
    engine = BacktestEngine(small_config, CostModel(), initial_equity=100_000.0)
    result = engine.run({"TEST": df}, benchmark_prices=benchmark_prices)

    assert "benchmark_equity" in result.equity_curve.columns
    assert result.equity_curve["benchmark_equity"].iloc[0] == pytest.approx(100_000.0)
    assert "benchmark_total_return_pct" in result.metrics
    assert "benchmark_cagr_pct" in result.metrics
    assert result.metrics["alpha_cagr_pct"] == pytest.approx(
        result.metrics["cagr_pct"] - result.metrics["benchmark_cagr_pct"]
    )


def test_no_benchmark_columns_when_benchmark_not_given(small_config, ohlcv_factory):
    df = ohlcv_factory([100.0 + i for i in range(60)])
    result = BacktestEngine(small_config).run({"TEST": df})
    assert "benchmark_equity" not in result.equity_curve.columns
    assert "benchmark_cagr_pct" not in result.metrics


def test_repeat_run_determinism(small_config, ohlcv_factory, dip_closes_factory):
    df = ohlcv_factory(dip_closes_factory(tail_bars=9))

    result_1 = BacktestEngine(small_config, CostModel()).run({"TEST": df})
    result_2 = BacktestEngine(small_config, CostModel()).run({"TEST": df})

    assert result_1.trades == result_2.trades
    assert result_1.pending_entries_at_end == result_2.pending_entries_at_end
    pd.testing.assert_frame_equal(result_1.equity_curve, result_2.equity_curve)
    assert result_1.metrics.keys() == result_2.metrics.keys()
    for key, value_1 in result_1.metrics.items():
        value_2 = result_2.metrics[key]
        if isinstance(value_1, float) and math.isnan(value_1):
            assert math.isnan(value_2), f"{key}: {value_1!r} != {value_2!r}"
        else:
            assert value_1 == value_2, f"{key}: {value_1!r} != {value_2!r}"
    assert result_1.final_equity == result_2.final_equity
