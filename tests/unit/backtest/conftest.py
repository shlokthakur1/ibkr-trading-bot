from __future__ import annotations

import pandas as pd
import pytest

from ibkr_bot.strategy import StrategyConfig


@pytest.fixture
def small_config() -> StrategyConfig:
    """Same shape as tests/unit/strategy/conftest.py's small_config — short windows so a small
    synthetic fixture exercises real signals.
    """
    return StrategyConfig(
        sma_trend_period=20,
        trend_slope_lookback=5,
        mean_window=10,
        entry_z_min=-3.0,
        entry_z_max=-0.5,
        rsi_period=10,
        rsi_crash_floor=10.0,
        rsi_oversold_max=60.0,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        time_stop_bars=5,
        position_size_pct_equity=0.10,
        max_concurrent_positions=8,
        min_bars_warmup=20,
    )


def make_ohlcv(closes: list[float], daily_range_pct: float = 0.001) -> pd.DataFrame:
    """Build an OHLCV panel with a small, symmetric daily high/low range around each close —
    enough for TP/SL touch-detection tests without close itself needing to hit the level.
    """
    index = pd.date_range("2020-01-01", periods=len(closes), freq="B")
    high = [c * (1 + daily_range_pct) for c in closes]
    low = [c * (1 - daily_range_pct) for c in closes]
    return pd.DataFrame(
        {"open": closes, "high": high, "low": low, "close": closes}, index=index
    )


@pytest.fixture
def ohlcv_factory():
    return make_ohlcv


def dip_in_uptrend_closes(tail_bars: int = 9) -> list[float]:
    """Same crafted scenario as tests/unit/strategy — 30-bar uptrend, 6-bar dip, then resumes.
    `tail_bars` controls how much post-dip data is generated (more bars => more room for a
    time-stop or a later touch to play out).
    """
    closes = [100.0 + i * 1.0 for i in range(30)]
    closes += [closes[-1] - i * 1.5 for i in range(1, 7)]
    closes += [closes[-1] + i * 1.0 for i in range(1, tail_bars + 1)]
    return closes


@pytest.fixture
def dip_closes_factory():
    return dip_in_uptrend_closes
