import pytest

from ibkr_bot.strategy import StrategyConfig, config_hash, load_config


def test_config_hash_is_deterministic():
    cfg1 = StrategyConfig()
    cfg2 = StrategyConfig()
    assert config_hash(cfg1) == config_hash(cfg2)


def test_config_hash_changes_with_a_parameter():
    cfg1 = StrategyConfig()
    cfg2 = StrategyConfig(stop_loss_pct=0.06)
    assert config_hash(cfg1) != config_hash(cfg2)


def test_config_hash_is_stable_across_repeated_calls():
    cfg = StrategyConfig()
    assert config_hash(cfg) == config_hash(cfg) == config_hash(cfg)


def test_invalid_z_range_rejected():
    with pytest.raises(ValueError, match="entry_z_min"):
        StrategyConfig(entry_z_min=-1.0, entry_z_max=-3.0)


def test_invalid_rsi_range_rejected():
    with pytest.raises(ValueError, match="rsi_crash_floor"):
        StrategyConfig(rsi_crash_floor=50.0, rsi_oversold_max=40.0)


def test_warmup_shorter_than_trend_period_rejected():
    with pytest.raises(ValueError, match="min_bars_warmup"):
        StrategyConfig(sma_trend_period=200, min_bars_warmup=50)


def test_load_config_from_yaml(tmp_path):
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("stop_loss_pct: 0.04\ntake_profit_pct: 0.08\n")
    cfg = load_config(yaml_path)
    assert cfg.stop_loss_pct == 0.04
    assert cfg.take_profit_pct == 0.08
    assert cfg.sma_trend_period == 200  # untouched fields keep their default


def test_load_config_rejects_unknown_key(tmp_path):
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("not_a_real_field: 1\n")
    with pytest.raises(ValueError, match="Unknown StrategyConfig key"):
        load_config(yaml_path)
