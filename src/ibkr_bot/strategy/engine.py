"""StrategyEngine: the mode-agnostic core of strategy v1.

Two methods matter:
  - prepare(df)          vectorized indicator computation over a full OHLCV panel.
  - decide(prepared, i, in_position, symbol)
                          pure per-bar decision, reading only row i (and earlier, via the
                          already-backward-looking indicator columns) — this is the "on_bar"
                          function a live/paper SignalRouter calls once per new bar, supplying
                          `in_position` from the broker's own truth (ExecutionContext.
                          current_position(), see plan §2.6), and it's exactly what a backtest
                          engine (Phase 3) calls too, supplying `in_position` from its own
                          portfolio ledger. Nothing here ever needs to guess position state on
                          its own — that's deliberately left to the caller, which is what keeps
                          this class free of any broker/backtest-specific bookkeeping.
"""

from __future__ import annotations

import pandas as pd

from . import signals as sig
from .config import StrategyConfig, config_hash
from .types import TargetPosition


class StrategyEngine:
    def __init__(self, config: StrategyConfig):
        self.config = config
        self._config_hash = config_hash(config)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add every indicator/entry-condition column to a copy of `df`. Pure function of df.

        Raises ValueError on a missing OHLCV column or a non-ascending index rather than
        silently producing garbage signals.
        """
        missing = sig.REQUIRED_OHLCV_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"OHLCV panel missing required column(s): {sorted(missing)}")
        if not df.index.is_monotonic_increasing:
            raise ValueError("OHLCV panel index must be sorted ascending (oldest bar first)")
        return sig.compute_indicators(df, self.config)

    def decide(
        self, prepared: pd.DataFrame, i: int, in_position: bool, symbol: str
    ) -> TargetPosition | None:
        """Return a TargetPosition if bar `i` of `prepared` is a valid entry, else None.

        `in_position` and `i < min_bars_warmup` are checked here (not baked into entry_raw) so
        the raw entry-condition series (`entry_signal_series`) stays a pure reflection of the
        market data alone, useful on its own for research/testing.
        """
        if in_position or i < self.config.min_bars_warmup:
            return None
        if not bool(prepared["entry_raw"].iloc[i]):
            return None

        row = prepared.iloc[i]
        idx = prepared.index[i]
        as_of = idx.date() if hasattr(idx, "date") else idx
        return TargetPosition(
            symbol=symbol,
            as_of_date=as_of,
            side="LONG",
            target_weight=self.config.position_size_pct_equity,
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_pct=self.config.take_profit_pct,
            time_stop_bars=self.config.time_stop_bars,
            reason="entry: dip+uptrend+rsi",
            strategy_id=self.config.strategy_id,
            config_hash=self._config_hash,
            z_score=float(row["zscore"]) if pd.notna(row["zscore"]) else float("nan"),
            rsi=float(row["rsi"]) if pd.notna(row["rsi"]) else float("nan"),
        )

    def entry_signal_series(self, prepared: pd.DataFrame) -> pd.Series:
        """The vectorized, position-state-agnostic entry condition (the `entry_raw` column)."""
        return prepared["entry_raw"]
