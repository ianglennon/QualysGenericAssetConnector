"""Tests for GET /health endpoint — readiness gating and DB connectivity check.

Requirements: HLTH-01, HLTH-02
"""
import app.main as main_module
from app.main import app
from fastapi.testclient import TestClient


def test_health_returns_503_before_ready(monkeypatch):
    """Health endpoint returns 503 with {status: starting} while _app_ready is False."""
    with TestClient(app, raise_server_exceptions=False) as client:
        # Override _app_ready to False after lifespan has set it True
        monkeypatch.setattr(main_module, "_app_ready", False)
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"status": "starting"}


def test_health_returns_200_when_ready():
    """Health endpoint returns 200 with {status: ok, db: ok} after lifespan completes."""
    with TestClient(app, raise_server_exceptions=False) as client:
        # _app_ready is True after lifespan runs
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"


def test_health_includes_db_check():
    """Health response body contains 'db' key with value 'ok'."""
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert "db" in response.json()
        assert response.json()["db"] == "ok"


def test_health_no_auth_required():
    """GET /health returns 200 without any Authorization header."""
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/health")
        assert response.status_code not in (401, 403)


def test_app_ready_false_after_shutdown():
    """_app_ready flag is reset to False after lifespan shutdown."""
    with TestClient(app, raise_server_exceptions=False) as client:
        # Inside context: _app_ready should be True
        assert main_module._app_ready is True
    # After exiting context manager, lifespan shutdown runs
    assert main_module._app_ready is False
