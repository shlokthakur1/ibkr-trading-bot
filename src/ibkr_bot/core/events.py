"""Broker-agnostic domain event types.

These are the only shapes that cross the boundary between `broker/` (which knows about
ib_async) and everything else (`execution/`, `risk/`, `persistence/`, `dashboard/`) — a mapper in
`broker/ibkr/mappers.py` (Phase 7) will translate ib_async objects into these, and nothing
outside `broker/` ever touches an ib_async object directly. This module itself must never import
ib_async or asyncio; see the package docstring in `core/__init__.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Bar:
    """One OHLCV bar for a symbol."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Tick:
    """One trade or quote tick, as aggregated into bars by data/bar_aggregator.py (Phase 8)."""

    symbol: str
    timestamp: datetime
    price: float
    size: float


@dataclass(frozen=True)
class Fill:
    """One executed order fill, as reported by the broker's commission/execution events."""

    symbol: str
    timestamp: datetime
    side: Side
    quantity: float
    price: float
    commission: float
    order_id: str
    realized_pnl: float | None = None


@dataclass(frozen=True)
class Position:
    """A symbol's current open position, as queried live from the broker (never tracked
    locally — see the architecture plan §2.5's "query IB live, never track state locally"
    principle, ported from the earlier prototype's trader.py:202-212).
    """

    symbol: str
    quantity: float
    avg_price: float
    market_price: float | None = None
    unrealized_pnl: float | None = None


@dataclass(frozen=True)
class AccountSnapshot:
    """A point-in-time account summary, as queried live from the broker."""

    timestamp: datetime
    account_id: str
    net_liquidation: float
    buying_power: float
    cash: float
    currency: str
