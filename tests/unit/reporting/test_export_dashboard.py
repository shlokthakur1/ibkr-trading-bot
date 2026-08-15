"""export_backtest_result must produce exactly the allow-listed JSON files/fields the dashboard
API reads — never a raw dump of internal run objects (plan §2.9)."""

from __future__ import annotations

import json
import math
from datetime import date

import pandas as pd
import pytest

from ibkr_bot.backtest.costs import CostModel
from ibkr_bot.backtest.engine import BacktestEngine
from ibkr_bot.data.universe import Universe, UniverseEntry
from ibkr_bot.reporting import export_backtest_result
from ibkr_bot.strategy import StrategyConfig


@pytest.fixture
def tiny_universe() -> Universe:
    return Universe(
        as_of_date=date(2026, 1, 1),
        review_cadence="quarterly-manual",
        source_note="test",
        entries=(
            UniverseEntry(
                symbol="TEST",
                exchange="ASX",
                currency="AUD",
                sector="Financials",
                name="Test Co",
                added_date=date(2026, 1, 1),
                min_history_years=5,
            ),
        ),
    )


def _small_config() -> StrategyConfig:
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


def _dip_ohlcv() -> pd.DataFrame:
    closes = [100.0 + i * 1.0 for i in range(30)]
    closes += [closes[-1] - i * 1.5 for i in range(1, 7)]
    closes += [closes[-1] + i * 1.0 for i in range(1, 10)]
    index = pd.date_range("2020-01-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes}, index=index
    )


def test_export_writes_all_expected_files(tmp_path, tiny_universe):
    result = BacktestEngine(_small_config(), CostModel()).run({"TEST": _dip_ohlcv()})
    export_backtest_result(result, tiny_universe, tmp_path, run_id="test-run")

    expected_files = {
        "status.json",
        "metrics.json",
        "equity_curve.json",
        "trades.json",
        "universe.json",
        "pending_signals.json",
    }
    assert {p.name for p in tmp_path.iterdir()} == expected_files


def test_status_json_schema(tmp_path, tiny_universe):
    result = BacktestEngine(_small_config(), CostModel()).run({"TEST": _dip_ohlcv()})
    export_backtest_result(result, tiny_universe, tmp_path, run_id="test-run", mode="backtest")

    status = json.loads((tmp_path / "status.json").read_text())
    assert status["run_id"] == "test-run"
    assert status["mode"] == "backtest"
    assert status["symbols"] == ["TEST"]
    assert status["config_hash"] == result.config_hash
    assert "start" in status["data_period"] and "end" in status["data_period"]


def test_trades_json_has_only_allowlisted_fields(tmp_path, tiny_universe):
    result = BacktestEngine(_small_config(), CostModel()).run({"TEST": _dip_ohlcv()})
    export_backtest_result(result, tiny_universe, tmp_path, run_id="test-run")

    trades = json.loads((tmp_path / "trades.json").read_text())
    assert len(trades) == 1
    allowed = {
        "symbol", "entry_date", "entry_price", "exit_date", "exit_price", "exit_reason",
        "quantity", "gross_pnl", "costs", "net_pnl", "r_multiple", "bars_held",
        "z_score_at_entry", "rsi_at_entry",
    }
    assert set(trades[0].keys()) == allowed
    assert trades[0]["symbol"] == "TEST"


def test_nan_metrics_become_json_null_not_nan_string(tmp_path, tiny_universe):
    # profit_factor is NaN whenever there are no losing trades (see backtest/metrics.py) —
    # exactly the case for this crafted scenario's single winning-or-timed-out trade set.
    result = BacktestEngine(_small_config(), CostModel()).run({"TEST": _dip_ohlcv()})
    export_backtest_result(result, tiny_universe, tmp_path, run_id="test-run")

    raw_text = (tmp_path / "metrics.json").read_text()
    assert "NaN" not in raw_text  # real JSON has no NaN literal — must be null
    metrics = json.loads(raw_text)
    if math.isnan(result.metrics["profit_factor"]):
        assert metrics["profit_factor"] is None


def test_pending_signals_json_reflects_unfilled_final_bar_signal(tmp_path, tiny_universe):
    closes = [100.0 + i * 1.0 for i in range(30)]
    closes += [closes[-1] - i * 1.5 for i in range(1, 7)]  # entry fires on the last of these
    df = pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes},
        index=pd.date_range("2020-01-01", periods=len(closes), freq="B"),
    )
    result = BacktestEngine(_small_config(), CostModel()).run({"TEST": df})
    export_backtest_result(result, tiny_universe, tmp_path, run_id="test-run")

    pending = json.loads((tmp_path / "pending_signals.json").read_text())
    assert len(pending) == len(result.pending_entries_at_end)
    if pending:
        assert pending[0]["symbol"] == "TEST"
        assert pending[0]["side"] == "LONG"


def test_universe_json_only_exposes_symbol_sector_name(tmp_path, tiny_universe):
    result = BacktestEngine(_small_config(), CostModel()).run({"TEST": _dip_ohlcv()})
    export_backtest_result(result, tiny_universe, tmp_path, run_id="test-run")

    universe_out = json.loads((tmp_path / "universe.json").read_text())
    assert universe_out == [{"symbol": "TEST", "sector": "Financials", "name": "Test Co"}]
