"""Pure, strictly backward-looking indicator functions.

Every function here reads only `series[:i+1]` to produce its value at index i (rolling windows
and shifts are inherently backward-only) — that's what guarantees vectorized-over-history and
bar-by-bar streaming replay produce identical values at every index (see plan §2.2, "determinism
guarantees", and tests/unit/strategy/test_engine.py's streaming-vs-vectorized equivalence test).

No classes, no hidden state, no wall-clock reads, no randomness.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average. NaN until `period` values are available (no partial windows)."""
    return series.rolling(window=period, min_periods=period).mean()


def rolling_std(series: pd.Series, period: int) -> pd.Series:
    """Rolling population standard deviation (ddof=0) — deterministic, no partial windows."""
    return series.rolling(window=period, min_periods=period).std(ddof=0)


def zscore(series: pd.Series, period: int) -> pd.Series:
    """(value - rolling mean) / rolling std over the same window. NaN where std is 0 or NaN."""
    mean = sma(series, period)
    std = rolling_std(series, period)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (series - mean) / std.replace(0.0, np.nan)
    return z


def sma_slope(sma_series: pd.Series, lookback: int) -> pd.Series:
    """sma_series[t] - sma_series[t - lookback]. Positive means the average is rising."""
    return sma_series - sma_series.shift(lookback)


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Classic Wilder RSI: simple-average seed over the first `period` deltas, then Wilder's
    recursive smoothing (avg = (prev_avg * (period - 1) + current) / period) for every bar after.

    Implemented as an explicit recursion (not pandas .ewm) so the exact seeding/smoothing matches
    the textbook definition bit-for-bit and isn't coupled to pandas' ewm internals — this is the
    version most charting platforms compute, and it's what the determinism tests pin against.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    n = len(close)
    avg_gain = pd.Series(np.nan, index=close.index, dtype=float)
    avg_loss = pd.Series(np.nan, index=close.index, dtype=float)
    if n <= period:
        return pd.Series(np.nan, index=close.index)

    avg_gain.iloc[period] = gain.iloc[1 : period + 1].mean()
    avg_loss.iloc[period] = loss.iloc[1 : period + 1].mean()
    for i in range(period + 1, n):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    rsi = rsi.where(~(avg_gain == 0.0) | ~(avg_loss == 0.0), 50.0)
    return rsi
