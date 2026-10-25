"""Export a BacktestResult to the small set of JSON files the local dashboard reads.

This is the *only* place a run's internal data is turned into what the dashboard sees — always
an explicit, allow-listed projection (never "dump the object"), so nothing beyond symbol/price/
date/metric fields can ever end up here even if a future run object carries more (plan §2.9).
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path

from ibkr_bot.backtest.engine import BacktestResult
from ibkr_bot.data.universe import Universe


def _clean(value):
    """NaN isn't valid JSON — represent it as null, which the frontend already treats as
    "no value" for a metric."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str))


def export_backtest_result(
    result: BacktestResult,
    universe: Universe,
    output_dir: str | Path,
    run_id: str,
    mode: str = "backtest",
    generated_at: datetime | None = None,
) -> None:
    """Write status.json, metrics.json, equity_curve.json, trades.json, universe.json into
    `output_dir`. The dashboard API (dashboard/api.py) reads these back on every request, so
    re-running a backtest and re-exporting is all that's needed to refresh what it shows.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = generated_at or datetime.now().astimezone()

    metrics = {k: _clean(v) for k, v in result.metrics.items()}
    _write_json(
        output_dir / "metrics.json",
        {
            **metrics,
            "config_hash": result.config_hash,
            "initial_equity": result.initial_equity,
            "final_equity": result.final_equity,
        },
    )

    equity_records = result.equity_curve.reset_index().to_dict(orient="records")
    for row in equity_records:
        row["date"] = row["date"].date().isoformat() if hasattr(row["date"], "date") else str(
            row["date"]
        )
        for key, value in list(row.items()):
            row[key] = _clean(value)
    _write_json(output_dir / "equity_curve.json", equity_records)

    trades = []
    for t in result.trades:
        trades.append(
            {
                "symbol": t.symbol,
                "entry_date": t.entry_date.isoformat()
                if isinstance(t.entry_date, date)
                else str(t.entry_date),
                "entry_price": _clean(t.entry_price),
                "exit_date": t.exit_date.isoformat()
                if isinstance(t.exit_date, date)
                else str(t.exit_date),
                "exit_price": _clean(t.exit_price),
                "exit_reason": t.exit_reason,
                "quantity": t.quantity,
                "gross_pnl": _clean(t.gross_pnl),
                "costs": _clean(t.costs),
                "net_pnl": _clean(t.net_pnl),
                "r_multiple": _clean(t.r_multiple),
                "bars_held": t.bars_held,
                "z_score_at_entry": _clean(t.z_score_at_entry),
                "rsi_at_entry": _clean(t.rsi_at_entry),
            }
        )
    _write_json(output_dir / "trades.json", trades)

    universe_records = [
        {"symbol": e.symbol, "sector": e.sector, "name": e.name}
        for e in universe.entries
    ]
    _write_json(output_dir / "universe.json", universe_records)

    pending_signals = [
        {
            "symbol": p.symbol,
            "as_of_date": p.as_of_date.isoformat()
            if isinstance(p.as_of_date, date)
            else str(p.as_of_date),
            "side": p.side,
            "reason": p.reason,
            "z_score": _clean(p.z_score),
            "rsi": _clean(p.rsi),
        }
        for p in getattr(result, "pending_entries_at_end", [])
    ]
    _write_json(output_dir / "pending_signals.json", pending_signals)

    _write_json(
        output_dir / "status.json",
        {
            "run_id": run_id,
            "mode": mode,
            "generated_at": generated_at.isoformat(),
            "config_hash": result.config_hash,
            "symbols": result.symbols,
            "data_period": {
                "start": equity_records[0]["date"] if equity_records else None,
                "end": equity_records[-1]["date"] if equity_records else None,
            },
        },
    )
