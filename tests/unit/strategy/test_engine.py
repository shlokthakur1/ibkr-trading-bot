"""Determinism tests for StrategyEngine — the acceptance bar for Phase 1 (plan §Verification).

Covers: indicator/entry correctness on a crafted scenario, the position/warmup gates, the
streaming-vs-vectorized equivalence (no lookahead), and repeat-run byte-identical determinism.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ibkr_bot.strategy import StrategyEngine


def _dip_in_uptrend_closes() -> list[float]:
    """30 bars of a steady uptrend, a 6-bar pullback shallow enough to stay above the 20-period
    trend SMA while dropping well below the 10-period mean SMA (a genuine "dip", not a trend
    break), then a resumed uptrend. Verified by inspection to trigger exactly one entry under
    `small_config` (uptrend + dip + RSI all align on one bar, and only one).
    """
    closes = [100.0 + i * 1.0 for i in range(30)]
    closes += [closes[-1] - i * 1.5 for i in range(1, 7)]
    closes += [closes[-1] + i * 1.0 for i in range(1, 10)]
    return closes


def test_entry_fires_exactly_once_on_crafted_dip(small_config, ohlcv_factory):
    df = ohlcv_factory(_dip_in_uptrend_closes())
    engine = StrategyEngine(small_config)
    prepared = engine.prepare(df)

    assert prepared["entry_raw"].sum() == 1
    entry_positions = prepared.index[prepared["entry_raw"]]
    (entry_date,) = entry_positions
    i = prepared.index.get_loc(entry_date)

    decision = engine.decide(prepared, i, in_position=False, symbol="TEST")
    assert decision is not None
    assert decision.symbol == "TEST"
    assert decision.side == "LONG"
    assert decision.as_of_date == entry_date.date()
    assert decision.stop_loss_pct == small_config.stop_loss_pct
    assert decision.take_profit_pct == small_config.take_profit_pct
    assert decision.time_stop_bars == small_config.time_stop_bars
    assert small_config.entry_z_min <= decision.z_score <= small_config.entry_z_max
    assert small_config.rsi_crash_floor <= decision.rsi <= small_config.rsi_oversold_max


def test_decide_returns_none_while_in_position(small_config, ohlcv_factory):
    df = ohlcv_factory(_dip_in_uptrend_closes())
    engine = StrategyEngine(small_config)
    prepared = engine.prepare(df)
    i = prepared.index.get_loc(prepared.index[prepared["entry_raw"]][0])

    assert engine.decide(prepared, i, in_position=True, symbol="TEST") is None
    assert engine.decide(prepared, i, in_position=False, symbol="TEST") is not None


def test_decide_returns_none_before_warmup(small_config, ohlcv_factory):
    df = ohlcv_factory(_dip_in_uptrend_closes())
    engine = StrategyEngine(small_config)
    prepared = engine.prepare(df)

    for i in range(small_config.min_bars_warmup):
        assert engine.decide(prepared, i, in_position=False, symbol="TEST") is None


def test_decide_never_fires_when_entry_raw_is_false(small_config, ohlcv_factory):
    df = ohlcv_factory(_dip_in_uptrend_closes())
    engine = StrategyEngine(small_config)
    prepared = engine.prepare(df)

    non_entry_indices = [i for i in range(len(prepared)) if not prepared["entry_raw"].iloc[i]]
    for i in non_entry_indices:
        assert engine.decide(prepared, i, in_position=False, symbol="TEST") is None


def test_prepare_rejects_missing_columns(small_config):
    engine = StrategyEngine(small_config)
    bad_df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="missing required column"):
        engine.prepare(bad_df)


def test_prepare_rejects_unsorted_index(small_config, ohlcv_factory):
    engine = StrategyEngine(small_config)
    df = ohlcv_factory(_dip_in_uptrend_closes()).iloc[::-1]  # reverse to break ascending order
    with pytest.raises(ValueError, match="sorted ascending"):
        engine.prepare(df)


def test_repeat_run_determinism(small_config, ohlcv_factory):
    """Running prepare() twice on identical input must produce byte-identical output."""
    df = ohlcv_factory(_dip_in_uptrend_closes())
    engine = StrategyEngine(small_config)

    prepared_1 = engine.prepare(df)
    prepared_2 = StrategyEngine(small_config).prepare(df)  # fresh instance too

    pd.testing.assert_frame_equal(prepared_1, prepared_2)


def test_repeat_decide_sequence_determinism(small_config, ohlcv_factory):
    df = ohlcv_factory(_dip_in_uptrend_closes())
    engine = StrategyEngine(small_config)
    prepared = engine.prepare(df)

    def walk() -> list:
        decisions = []
        for i in range(len(prepared)):
            d = engine.decide(prepared, i, in_position=False, symbol="TEST")
            if d is not None:
                decisions.append(d)
        return decisions

    assert walk() == walk()


def test_streaming_vs_vectorized_equivalence_no_lookahead(small_config, ohlcv_factory):
    """The value of every indicator column at bar i, computed from the FULL panel, must match
    the value obtained by preparing only data[0:i+1] (a truncated panel) and reading its last
    row. This is the empirical guarantee that no indicator peeks at future bars.
    """
    closes = _dip_in_uptrend_closes()
    full_df = ohlcv_factory(closes)
    engine = StrategyEngine(small_config)
    full_prepared = engine.prepare(full_df)

    indicator_cols = ["sma_trend", "sma_trend_lag", "sma_mean", "std_mean", "zscore", "rsi"]

    # Sample a spread of truncation points, including right around the warmup boundary.
    check_points = sorted({small_config.min_bars_warmup, len(closes) // 2, len(closes) - 1})
    for i in check_points:
        truncated_df = full_df.iloc[: i + 1]
        truncated_prepared = engine.prepare(truncated_df)
        full_row = full_prepared.iloc[i]
        truncated_row = truncated_prepared.iloc[-1]
        for col in indicator_cols:
            full_val = full_row[col]
            trunc_val = truncated_row[col]
            if pd.isna(full_val) and pd.isna(trunc_val):
                continue
            assert full_val == pytest.approx(trunc_val), f"column {col!r} at i={i} diverged"
