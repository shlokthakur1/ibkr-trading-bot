"""Local, read-only FastAPI dashboard. Run with: uvicorn ibkr_bot.dashboard.app:app

Reads whatever reporting/export_dashboard.py has written to DASHBOARD_DATA_DIR (default
data/dashboard) — re-exporting a fresh run is all that's needed to update what this shows; the
server itself holds no state and needs no restart.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="ibkr-trading-bot dashboard",
        description="Local, read-only backtest/paper/live performance dashboard.",
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(router)  # API routes registered first — see StaticFiles note below.

    static_dir = Path(__file__).parent / "static"
    # Mounted last and at "/": FastAPI/Starlette match routes in registration order, so the
    # /api/* routes above are tried first and this only catches everything else (index.html and
    # any future static assets).
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


app = create_app()
