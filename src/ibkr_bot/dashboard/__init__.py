"""Read-only local FastAPI dashboard (GET-only routes) over the persistence/reporting layer.

Never imports broker/ or risk/'s live-order code paths. Run with:
`uvicorn ibkr_bot.dashboard.app:app --reload`.
"""

from .app import create_app

__all__ = ["create_app"]
