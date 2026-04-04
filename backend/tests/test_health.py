"""Tests for GET /health endpoint -- readiness gating and DB connectivity check.

Requirements: HLTH-01, HLTH-02

Uses shared conftest.py client fixture for standard health checks.
Tests that need to manipulate _app_ready use their own TestClient.
"""
import pytest
from unittest.mock import patch
import app.main as main_module
from app.main import app
from fastapi.testclient import TestClient


def test_health_returns_503_before_ready(client, monkeypatch):
    """Health endpoint returns 503 with {status: starting} while _app_ready is False."""
    monkeypatch.setattr(main_module, "_app_ready", False)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "starting"}


def test_health_returns_200_when_ready(client):
    """Health endpoint returns 200 with {status: ok, db: ok} after lifespan completes."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"


def test_health_includes_db_check(client):
    """Health response body contains 'db' key with value 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "db" in response.json()
    assert response.json()["db"] == "ok"


def test_health_no_auth_required(client):
    """GET /health returns 200 without any Authorization header."""
    response = client.get("/health")
    assert response.status_code not in (401, 403)


def test_app_ready_false_after_shutdown():
    """_app_ready flag is reset to False after lifespan shutdown.

    This test requires its own TestClient to observe lifespan exit behavior.
    """
    with (
        patch("app.main.run_migrations"),
        patch("app.main.verify_db_integrity"),
        patch("app.services.bootstrap_service.seed_admin_if_empty"),
        patch("app.scheduler.scheduler_service.init_scheduler"),
        patch("app.scheduler.scheduler_service.shutdown_scheduler"),
    ):
        with TestClient(app, raise_server_exceptions=False) as tc:
            # Inside context: _app_ready should be True
            assert main_module._app_ready is True
        # After exiting context manager, lifespan shutdown runs
        assert main_module._app_ready is False
