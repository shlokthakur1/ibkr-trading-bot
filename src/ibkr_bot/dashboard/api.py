"""Read-only JSON API over whatever a backtest/paper/live run has exported to disk.

Every route here is a GET that reads a static file written by reporting/export_dashboard.py —
there is no route that can place, cancel, or modify an order, and this module never imports
broker/ or risk/'s live-order code paths (plan §2.9/§2.10).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api")


def _data_dir() -> Path:
    return Path(os.environ.get("DASHBOARD_DATA_DIR", "data/dashboard"))


def _read_json(name: str):
    path = _data_dir() / name
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{name} not found under {_data_dir()} — has a backtest been exported yet?",
        )
    return json.loads(path.read_text())


@router.get("/status")
def get_status():
    return _read_json("status.json")


@router.get("/metrics")
def get_metrics():
    return _read_json("metrics.json")


@router.get("/equity-curve")
def get_equity_curve():
    return _read_json("equity_curve.json")


@router.get("/trades")
def get_trades():
    return _read_json("trades.json")


@router.get("/universe")
def get_universe():
    return _read_json("universe.json")


@router.get("/pending-signals")
def get_pending_signals():
    return _read_json("pending_signals.json")
