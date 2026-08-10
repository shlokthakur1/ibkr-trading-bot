"""Entry condition logic for strategy v1: healthy uptrend + dip (z-score) + RSI confirmation.

Each condition is its own small, independently testable function (matches the spec in the
architecture plan §2.2) operating on a DataFrame already carrying the indicator columns computed
by `compute_indicators`. Exit logic is intentionally *not* here — v1 only ever emits entries; see
strategy/types.py's module docstring for why.
"""

from __future__ import annotations

import pandas as pd

from . import indicators as ind
from .config import StrategyConfig

REQUIRED_OHLCV_COLUMNS = {"open", "high", "low", "close"}


def compute_indicators(df: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    """Add every indicator column strategy v1 needs. Pure function of (df, config)."""
    out = df.copy()
    out["sma_trend"] = ind.sma(out["close"], config.sma_trend_period)
    out["sma_trend_lag"] = out["sma_trend"].shift(config.trend_slope_lookback)
    out["sma_mean"] = ind.sma(out["close"], config.mean_window)
    out["std_mean"] = ind.rolling_std(out["close"], config.mean_window)
    out["zscore"] = ind.zscore(out["close"], config.mean_window)
    out["rsi"] = ind.wilder_rsi(out["close"], config.rsi_period)
    out["entry_raw"] = entry_signal(out, config)
    return out


def healthy_uptrend(df: pd.DataFrame) -> pd.Series:
    """close > sma_trend AND sma_trend itself rising over the configured lookback.

    NaN-safe by construction: numpy comparisons against NaN are False, so bars still in the
    trend-SMA warmup window naturally evaluate to False here, not True.
    """
    return (df["close"] > df["sma_trend"]) & (df["sma_trend"] > df["sma_trend_lag"])


def is_dip(df: pd.DataFrame, config: StrategyConfig) -> pd.Series:
    """z-score of price vs the rolling mean sits within [entry_z_min, entry_z_max]."""
    z = df["zscore"]
    return (z >= config.entry_z_min) & (z <= config.entry_z_max)


def rsi_confirms(df: pd.DataFrame, config: StrategyConfig) -> pd.Series:
    """RSI sits within [rsi_crash_floor, rsi_oversold_max] — oversold, not capitulating."""
    r = df["rsi"]
    return (r >= config.rsi_crash_floor) & (r <= config.rsi_oversold_max)


def entry_signal(df: pd.DataFrame, config: StrategyConfig) -> pd.Series:
    """Combined raw entry condition, ungated by any position state. NaN anywhere -> False."""
    raw = healthy_uptrend(df) & is_dip(df, config) & rsi_confirms(df, config)
    return raw.fillna(False)
