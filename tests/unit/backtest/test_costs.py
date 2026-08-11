import pytest

from ibkr_bot.backtest.costs import CostModel, round_to_tick, tick_size


def test_tick_size_bands():
    assert tick_size(0.05) == 0.001
    assert tick_size(0.099) == 0.001
    assert tick_size(0.10) == 0.005
    assert tick_size(1.99) == 0.005
    assert tick_size(2.00) == 0.01
    assert tick_size(100.0) == 0.01


def test_round_to_tick_snaps_to_nearest_valid_increment():
    assert round_to_tick(1.2223) == pytest.approx(1.220)  # 0.005 band -> nearest 0.005
    assert round_to_tick(1.2226) == pytest.approx(1.225)
    assert round_to_tick(50.001) == pytest.approx(50.00)  # 0.01 band
    assert round_to_tick(50.006) == pytest.approx(50.01)


def test_commission_uses_percentage_above_minimum():
    model = CostModel(commission_pct=0.0008, commission_min_aud=6.0)
    assert model.commission(100_000) == pytest.approx(80.0)  # 0.08% of 100k = $80 > min


def test_commission_floors_at_minimum():
    model = CostModel(commission_pct=0.0008, commission_min_aud=6.0)
    assert model.commission(1_000) == pytest.approx(6.0)  # 0.08% of 1000 = $0.80 < min


def test_entry_fill_price_slips_upward():
    model = CostModel(slippage_bps=0.001)
    filled = model.entry_fill_price(100.0)
    assert filled > 100.0
    assert filled == pytest.approx(round_to_tick(100.0 * 1.001))


def test_stop_fill_price_slips_downward():
    model = CostModel(slippage_bps=0.001)
    filled = model.stop_fill_price(50.0)
    assert filled < 50.0


def test_target_fill_price_has_no_slippage():
    model = CostModel(slippage_bps=0.001)
    assert model.target_fill_price(50.0) == round_to_tick(50.0)


def test_market_exit_fill_price_slips_downward():
    model = CostModel(slippage_bps=0.001)
    filled = model.market_exit_fill_price(75.0)
    assert filled < 75.0
