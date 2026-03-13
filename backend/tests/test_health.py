"""Tests for GET /health endpoint — readiness gating and DB connectivity check.

Requirements: HLTH-01, HLTH-02

Note: TestClient with lifespan=True runs the full application startup sequence.
In the test container the DB volume may be in a partial state, so we mock
bootstrap/scheduler calls that depend on specific tables being present.
"""
import pytest
from unittest.mock import patch
import app.main as main_module
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_lifespan_side_effects():
    """Prevent seed_admin_if_empty and init_scheduler from running in tests.

    The test container DB may not have user/scheduler tables ready, but
    that is orthogonal to the health endpoint behaviour we are testing.
    """
    with (
        patch("app.main.run_migrations"),
        patch("app.services.bootstrap_service.seed_admin_if_empty"),
        patch("app.scheduler.scheduler_service.init_scheduler"),
        patch("app.scheduler.scheduler_service.shutdown_scheduler"),
    ):
        yield


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
        # _app_ready is True after lifespan sets it
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
