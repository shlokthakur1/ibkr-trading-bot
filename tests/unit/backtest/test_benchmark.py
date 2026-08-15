import math

import pandas as pd
import pytest

from ibkr_bot.backtest.benchmark import benchmark_comparison, rebase_to_equity


def _dates(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2020-01-01", periods=n, freq="B")


def test_rebase_starts_at_initial_equity():
    index = _dates(5)
    prices = pd.Series([100.0, 102.0, 101.0, 105.0, 110.0], index=index)
    rebased = rebase_to_equity(prices, index, initial_equity=50_000.0)
    assert rebased.iloc[0] == pytest.approx(50_000.0)
    # scales proportionally: +10% in price -> +10% in rebased equity
    assert rebased.iloc[-1] == pytest.approx(50_000.0 * 1.10)


def test_rebase_forward_fills_interior_gaps():
    index = _dates(5)
    prices = pd.Series([100.0, 102.0, None, None, 110.0], index=index).dropna()
    rebased = rebase_to_equity(prices, index, initial_equity=100.0)
    # the two missing interior dates should carry forward the last known price (102.0)
    assert rebased.iloc[2] == pytest.approx(102.0)
    assert rebased.iloc[3] == pytest.approx(102.0)


def test_rebase_raises_if_leading_dates_are_missing():
    index = _dates(5)
    prices = pd.Series([102.0, 101.0, 105.0], index=index[2:])  # first two dates absent
    with pytest.raises(ValueError, match="no data"):
        rebase_to_equity(prices, index, initial_equity=100.0)


def test_rebase_raises_on_non_positive_first_price():
    index = _dates(3)
    prices = pd.Series([0.0, 1.0, 2.0], index=index)
    with pytest.raises(ValueError, match="positive"):
        rebase_to_equity(prices, index, initial_equity=100.0)


def test_benchmark_comparison_returns_metrics():
    index = _dates(253)  # ~1 trading year
    prices = pd.Series([100.0 * (1.0004**i) for i in range(253)], index=index)
    benchmark_equity, metrics = benchmark_comparison(prices, index, initial_equity=10_000.0)
    assert benchmark_equity.iloc[0] == pytest.approx(10_000.0)
    assert metrics["benchmark_total_return_pct"] > 0
    assert not math.isnan(metrics["benchmark_cagr_pct"])
