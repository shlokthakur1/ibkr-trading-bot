"""Dashboard API tests: read-only routes serving exported JSON — never a mutating route.

Uses fastapi.testclient.TestClient against a tmp_path data dir, isolated from any real repo
export via the DASHBOARD_DATA_DIR env var (see api.py's `_data_dir`).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from ibkr_bot.dashboard.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHBOARD_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def _write(tmp_path, name, payload):
    (tmp_path / name).write_text(json.dumps(payload))


def test_status_endpoint_returns_exported_json(client, tmp_path):
    _write(tmp_path, "status.json", {"run_id": "abc", "mode": "backtest"})
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json() == {"run_id": "abc", "mode": "backtest"}


def test_missing_export_returns_404_not_500(client):
    response = client.get("/api/metrics")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/status",
        "/api/metrics",
        "/api/equity-curve",
        "/api/trades",
        "/api/universe",
        "/api/pending-signals",
    ],
)
def test_every_api_route_rejects_mutating_verbs(client, path):
    for method in ("post", "put", "delete", "patch"):
        response = getattr(client, method)(path)
        assert response.status_code == 405, f"{method.upper()} {path} should not be allowed"


def test_index_html_is_served_at_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "ibkr-trading-bot" in response.text


def test_all_get_routes_are_read_only_by_construction():
    """Structural guard: enumerate the app's routes and assert none of them declare a
    mutating HTTP method — this is what actually enforces "read-only local dashboard", not
    just individual endpoint tests.
    """
    app = create_app()
    mutating = {"POST", "PUT", "DELETE", "PATCH"}
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        offending = methods & mutating
        assert not offending, f"route {route.path!r} declares mutating method(s) {offending}"
