"""Static GitHub Pages build tests: the built site must serve each export at the same relative
path the FastAPI app does, so the one index.html works under either host."""

from __future__ import annotations

import json

import pytest

from ibkr_bot.dashboard.api import ROUTE_FILES
from ibkr_bot.dashboard.build_site import STATIC_DIR, build_site


@pytest.fixture
def export_dir(tmp_path):
    data = tmp_path / "export"
    data.mkdir()
    for route, name in ROUTE_FILES.items():
        (data / name).write_text(json.dumps({"route": route}))
    return data


def test_every_route_is_written_at_its_api_path(export_dir, tmp_path):
    out = tmp_path / "site"
    build_site(export_dir, out)
    for route, name in ROUTE_FILES.items():
        assert (out / "api" / route).read_text() == (export_dir / name).read_text()


def test_index_html_is_copied(export_dir, tmp_path):
    out = tmp_path / "site"
    build_site(export_dir, out)
    assert "ibkr-trading-bot" in (out / "index.html").read_text(encoding="utf-8")


def test_missing_export_file_fails_the_build(export_dir, tmp_path):
    (export_dir / "trades.json").unlink()
    with pytest.raises(FileNotFoundError, match="trades.json"):
        build_site(export_dir, tmp_path / "site")


def test_frontend_fetches_relative_api_paths():
    """A leading slash would resolve to the github.io domain root, not the /ibkr-trading-bot/
    project subpath the page is served from."""
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for route in ROUTE_FILES:
        assert f"'api/{route}'" in html
        assert f"'/api/{route}'" not in html
