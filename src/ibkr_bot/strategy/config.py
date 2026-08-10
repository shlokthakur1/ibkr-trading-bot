"""Frozen, versioned strategy configuration.

Every parameter that affects signal generation lives here — never as a hardcoded constant in
indicators.py/signals.py/engine.py, and never read from an environment variable (env vars are
fine for connection/session settings elsewhere in the bot, but strategy *parameters* must be
part of a single, hashable, YAML-loadable object so a backtest run is fully reproducible from
{config file + git commit + data snapshot}). See plan §2.2/§2.9.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml


@dataclass(frozen=True)
class StrategyConfig:
    """Strategy v1: "buy the dip in a healthy uptrend" for ASX large caps.

    Defaults match the plan's recommended v1 parameters (§2.2). All fields are overridable via
    a YAML file loaded with load_config().
    """

    strategy_id: str = "asx_dip_v1"

    # Trend regime filter: close > sma_trend AND sma_trend itself rising over the lookback.
    sma_trend_period: int = 200
    trend_slope_lookback: int = 20

    # Dip identification: z-score of close vs its own rolling mean/std over `mean_window` bars.
    mean_window: int = 20
    entry_z_min: float = -3.0
    entry_z_max: float = -1.0

    # RSI confirmation (Wilder's, oversold-leaning but not capitulating).
    rsi_period: int = 14
    rsi_crash_floor: float = 20.0
    rsi_oversold_max: float = 40.0

    # Exit parameters (attached to the TargetPosition, enforced by the executor — see types.py).
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10
    time_stop_bars: int = 20

    # Sizing.
    position_size_pct_equity: float = 0.10
    max_concurrent_positions: int = 8

    # No signal is emitted before this many bars of history exist (defense in depth alongside
    # the NaN-driven warmup already inherent to rolling indicators — see engine.py).
    min_bars_warmup: int = 200

    def __post_init__(self) -> None:
        if self.entry_z_min >= self.entry_z_max:
            raise ValueError(
                f"entry_z_min ({self.entry_z_min}) must be < entry_z_max ({self.entry_z_max})"
            )
        if self.rsi_crash_floor >= self.rsi_oversold_max:
            raise ValueError(
                f"rsi_crash_floor ({self.rsi_crash_floor}) must be < "
                f"rsi_oversold_max ({self.rsi_oversold_max})"
            )
        if self.stop_loss_pct <= 0 or self.take_profit_pct <= 0:
            raise ValueError("stop_loss_pct and take_profit_pct must both be positive")
        if self.min_bars_warmup < self.sma_trend_period:
            raise ValueError("min_bars_warmup must be >= sma_trend_period")


def load_config(path: str | Path) -> StrategyConfig:
    """Load a StrategyConfig from a YAML file. Unknown keys raise (fail loudly on typos)."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    known = {f.name for f in fields(StrategyConfig)}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"Unknown StrategyConfig key(s) in {path}: {sorted(unknown)}")
    return StrategyConfig(**raw)


def config_hash(config: StrategyConfig) -> str:
    """A stable sha256 of the config's field values, for reproducibility (plan §2.2/§2.9).

    Deterministic across runs/processes: fields are serialized in declaration order via
    dataclasses.asdict, then json.dumps with sort_keys so key order never affects the hash.
    """
    payload = json.dumps(asdict(config), sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
