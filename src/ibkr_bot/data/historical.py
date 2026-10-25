"""Historical daily-bar fetch from IBKR, with a local CSV cache.

This is a deliberately minimal first pass at Phase 6 (built ahead of schedule to run a real
backtest against live Gateway data) — a single ad-hoc connection, no retry/backoff, no rate
limiter beyond the fixed pacing delay below. The full reconnection-hardened BrokerAdapter lands
properly in Phase 7; nothing here should be mistaken for that.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

# IBKR historical-data pacing: stay comfortably under the "no more than 6 requests per 2s per
# unique contract+bar-size" guideline documented in the API. See plan risk #7 — the proper
# limiter comes in Phase 7; this fixed delay is the minimal stand-in for now.
PACING_DELAY_SECONDS = 2.0


def fetch_daily_bars(
    ib, symbol: str, exchange: str, currency: str, duration: str = "2 Y"
) -> pd.DataFrame:
    """Fetch `duration` worth of daily OHLCV bars for one ASX symbol, ending now.

    `ib` is a connected ib_async.IB instance — this function doesn't manage the connection
    itself, matching the existing "IB is the source of truth, caller manages the session"
    principle carried over from the earlier prototype.
    """
    from ib_async import Stock

    contract = Stock(symbol, exchange, currency)
    qualified = ib.qualifyContracts(contract)
    if not qualified:
        raise ValueError(f"Could not qualify contract for {symbol} on {exchange}/{currency}")

    bars = ib.reqHistoricalData(
        qualified[0],
        endDateTime="",
        durationStr=duration,
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1,
    )
    if not bars:
        raise ValueError(f"No historical data returned for {symbol}")

    df = pd.DataFrame(
        {
            "date": [b.date for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df


def fetch_universe_daily_bars(
    ib,
    symbols: list[tuple[str, str, str]],
    duration: str = "2 Y",
    cache_dir: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Fetch daily bars for every (symbol, exchange, currency) tuple, pacing requests to avoid
    IBKR historical-data rate limits. Writes a CSV cache per symbol if `cache_dir` is given.
    """
    cache_path = Path(cache_dir) if cache_dir else None
    if cache_path:
        cache_path.mkdir(parents=True, exist_ok=True)

    panels: dict[str, pd.DataFrame] = {}
    for i, (symbol, exchange, currency) in enumerate(symbols):
        if i > 0:
            time.sleep(PACING_DELAY_SECONDS)
        df = fetch_daily_bars(ib, symbol, exchange, currency, duration=duration)
        panels[symbol] = df
        if cache_path:
            df.to_csv(cache_path / f"{symbol}.csv")
    return panels


def load_cached_daily_bars(cache_dir: str | Path, symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Load previously-cached CSVs instead of hitting IBKR again."""
    cache_path = Path(cache_dir)
    panels = {}
    for symbol in symbols:
        csv_path = cache_path / f"{symbol}.csv"
        df = pd.read_csv(csv_path, index_col="date", parse_dates=True)
        panels[symbol] = df
    return panels
