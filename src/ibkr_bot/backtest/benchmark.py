"""Align a benchmark price series (e.g. ASX200/STW) to a backtest's equity curve for comparison.

Sourcing the actual benchmark price data (IBKR historical bars, per the plan's IBKR-only data
decision) is a Phase 6 concern — this module only does the alignment/rebasing math, so it can be
built and tested now against any price series the caller provides.
"""

from __future__ import annotations

import pandas as pd

from .metrics import return_stats


def rebase_to_equity(
    benchmark_prices: pd.Series, index: pd.Index, initial_equity: float
) -> pd.Series:
    """Reindex `benchmark_prices` onto `index` and rescale so it starts at `initial_equity` —
    the standard "if I'd put the same starting capital in the benchmark" comparison.

    Only forward-fills gaps (a benchmark data point missing for one of the strategy's trading
    days, e.g. a data-source hiccup) — never back-fills, since that would leak a later price
    backward into an earlier date. Raises if any required date still has no value after that,
    rather than silently comparing against a gap.
    """
    aligned = benchmark_prices.reindex(index).ffill()
    missing = aligned[aligned.isna()]
    if not missing.empty:
        raise ValueError(
            f"benchmark_prices has no data (even after forward-fill) for "
            f"{len(missing)} required date(s), starting {missing.index[0]}"
        )
    first_price = float(aligned.iloc[0])
    if first_price <= 0:
        raise ValueError(f"benchmark_prices' first value must be positive, got {first_price}")
    return aligned / first_price * initial_equity


def benchmark_comparison(
    benchmark_prices: pd.Series, equity_curve_index: pd.Index, initial_equity: float
) -> tuple[pd.Series, dict]:
    """Returns (rebased benchmark equity series, comparison metrics dict)."""
    benchmark_equity = rebase_to_equity(benchmark_prices, equity_curve_index, initial_equity)
    total_return_pct, cagr_pct = return_stats(benchmark_equity)
    return benchmark_equity, {
        "benchmark_total_return_pct": total_return_pct,
        "benchmark_cagr_pct": cagr_pct,
    }
