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

# Route -> the file export_dashboard.py writes for it. The single source of truth for both this
# API and the static GitHub Pages build (build_site.py), so the two can never serve different
# things under the same path.
ROUTE_FILES = {
    "status": "status.json",
    "metrics": "metrics.json",
    "equity-curve": "equity_curve.json",
    "trades": "trades.json",
    "universe": "universe.json",
    "pending-signals": "pending_signals.json",
}


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


def _endpoint_for(name: str):
    def endpoint():
        return _read_json(name)

    return endpoint


for _route, _name in ROUTE_FILES.items():
    router.add_api_route(f"/{_route}", _endpoint_for(_name), methods=["GET"], name=_route)
