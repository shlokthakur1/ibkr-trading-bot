"""Shared fixtures for strategy-engine unit tests."""

from __future__ import annotations

import pandas as pd
import pytest

from ibkr_bot.strategy import StrategyConfig


@pytest.fixture
def small_config() -> StrategyConfig:
    """A StrategyConfig with short windows so small synthetic fixtures exercise real signals
    without needing hundreds of bars. Values are otherwise the same shape as the v1 defaults.
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


def make_ohlcv(closes: list[float]) -> pd.DataFrame:
    """Build a minimal OHLCV panel from a list of closes (open=high=low=close for simplicity —
    entry-signal logic in v1 only reads `close`; high/low matter for exit-fill simulation, which
    is a Phase 3 concern, not tested here).
    """
    index = pd.date_range("2020-01-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes}, index=index
    )


@pytest.fixture
def ohlcv_factory():
    """Returns `make_ohlcv` so tests can build a panel from an arbitrary closes list."""
    return make_ohlcv
