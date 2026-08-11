from ibkr_bot.backtest.fills import detect_intrabar_exit
from ibkr_bot.strategy.types import ExitReason


def test_no_exit_when_neither_level_touched():
    assert detect_intrabar_exit(bar_high=105, bar_low=95, stop_price=90, target_price=110) is None


def test_stop_only():
    result = detect_intrabar_exit(bar_high=100, bar_low=89, stop_price=90, target_price=110)
    assert result == ExitReason.STOP_LOSS


def test_target_only():
    result = detect_intrabar_exit(bar_high=111, bar_low=100, stop_price=90, target_price=110)
    assert result == ExitReason.TAKE_PROFIT


def test_both_touched_same_bar_stop_wins():
    result = detect_intrabar_exit(bar_high=115, bar_low=85, stop_price=90, target_price=110)
    assert result == ExitReason.STOP_LOSS


def test_exact_boundary_touches_count_as_hits():
    assert detect_intrabar_exit(bar_high=100, bar_low=90, stop_price=90, target_price=200) == (
        ExitReason.STOP_LOSS
    )
    assert detect_intrabar_exit(bar_high=110, bar_low=100, stop_price=0, target_price=110) == (
        ExitReason.TAKE_PROFIT
    )
