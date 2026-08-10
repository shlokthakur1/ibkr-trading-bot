"""Broker-agnostic domain event types (Bar, Tick, Fill, Position, AccountSnapshot).

Populated starting Phase 2 (see plan §2.1/§3). This package must never import ib_async or
asyncio — that boundary is what keeps the strategy engine and risk layer broker-agnostic.
"""
