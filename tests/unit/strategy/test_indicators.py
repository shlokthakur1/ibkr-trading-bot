import math

import numpy as np
import pandas as pd
import pytest

from ibkr_bot.strategy import indicators as ind


def test_sma_hand_computed():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = ind.sma(s, period=3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(2.0)  # mean(1,2,3)
    assert result.iloc[3] == pytest.approx(3.0)  # mean(2,3,4)
    assert result.iloc[4] == pytest.approx(4.0)  # mean(3,4,5)


def test_rolling_std_hand_computed():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = ind.rolling_std(s, period=3)
    # population std (ddof=0) of [1,2,3] is sqrt(2/3)
    assert result.iloc[2] == pytest.approx(math.sqrt(2.0 / 3.0))


def test_zscore_matches_manual_formula():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 10.0])
    z = ind.zscore(s, period=3)
    mean = s.rolling(3, min_periods=3).mean()
    std = s.rolling(3, min_periods=3).std(ddof=0)
    expected = (s - mean) / std
    pd.testing.assert_series_equal(z, expected, check_names=False)


def test_zscore_is_nan_when_std_is_zero():
    s = pd.Series([5.0, 5.0, 5.0, 5.0])
    z = ind.zscore(s, period=3)
    assert z.iloc[2:].isna().all()


def test_sma_slope_is_difference_from_lagged_value():
    s = pd.Series([1.0, 2.0, 4.0, 8.0, 16.0])
    slope = ind.sma_slope(s, lookback=2)
    assert np.isnan(slope.iloc[0])
    assert np.isnan(slope.iloc[1])
    assert slope.iloc[2] == pytest.approx(4.0 - 1.0)
    assert slope.iloc[3] == pytest.approx(8.0 - 2.0)
    assert slope.iloc[4] == pytest.approx(16.0 - 4.0)


def _reference_wilder_rsi(closes: list[float], period: int) -> list[float]:
    """Independent, unoptimized textbook implementation to check ind.wilder_rsi against."""
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    out = [float("nan")] * len(closes)
    if len(closes) <= period:
        return out

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rs = math.inf if avg_loss == 0 else avg_gain / avg_loss
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + rs)

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0 and avg_gain == 0:
            out[i + 1] = 50.0
        elif avg_loss == 0:
            out[i + 1] = 100.0
        else:
            out[i + 1] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def test_wilder_rsi_matches_independent_reference_implementation():
    closes = [44.0, 44.5, 43.5, 45.0, 45.5, 46.0, 45.8, 46.5, 47.2, 46.9, 47.5, 48.0]
    period = 3
    got = ind.wilder_rsi(pd.Series(closes), period=period)
    expected = _reference_wilder_rsi(closes, period=period)
    for i, exp in enumerate(expected):
        if math.isnan(exp):
            assert math.isnan(got.iloc[i]), f"index {i}"
        else:
            assert got.iloc[i] == pytest.approx(exp, abs=1e-9), f"index {i}"


def test_wilder_rsi_flat_prices_is_neutral_fifty():
    closes = [50.0] * 20
    rsi = ind.wilder_rsi(pd.Series(closes), period=5)
    assert rsi.iloc[5:].apply(lambda v: v == pytest.approx(50.0)).all()


def test_wilder_rsi_nan_during_warmup():
    closes = list(range(1, 10))
    rsi = ind.wilder_rsi(pd.Series([float(c) for c in closes]), period=5)
    assert rsi.iloc[:5].isna().all()
