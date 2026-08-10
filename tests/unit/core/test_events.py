"""Sanity checks for the broker-agnostic domain event types (plan §2.1)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from ibkr_bot.core import AccountSnapshot, Bar, Fill, Position, Tick


def test_bar_is_frozen():
    bar = Bar(
        symbol="CBA",
        timestamp=datetime(2026, 1, 1),
        open=1,
        high=2,
        low=0.5,
        close=1.5,
        volume=100,
    )
    with pytest.raises(FrozenInstanceError):
        bar.close = 2.0  # type: ignore[misc]


def test_tick_fields():
    tick = Tick(symbol="CBA", timestamp=datetime(2026, 1, 1), price=100.0, size=10)
    assert tick.symbol == "CBA"
    assert tick.price == 100.0


def test_fill_defaults_realized_pnl_to_none():
    fill = Fill(
        symbol="CBA",
        timestamp=datetime(2026, 1, 1),
        side="BUY",
        quantity=100,
        price=99.5,
        commission=6.0,
        order_id="1",
    )
    assert fill.realized_pnl is None
    assert fill.side == "BUY"


def test_position_optional_fields_default_to_none():
    pos = Position(symbol="CBA", quantity=100, avg_price=99.5)
    assert pos.market_price is None
    assert pos.unrealized_pnl is None


def test_account_snapshot_fields():
    snap = AccountSnapshot(
        timestamp=datetime(2026, 1, 1),
        account_id="DU12345",
        net_liquidation=100_000.0,
        buying_power=200_000.0,
        cash=50_000.0,
        currency="AUD",
    )
    assert snap.currency == "AUD"
    assert snap.net_liquidation == 100_000.0
