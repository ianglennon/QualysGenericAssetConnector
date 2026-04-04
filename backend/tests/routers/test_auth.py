"""Tests for authentication endpoints.

Uses shared conftest.py fixtures for DB and client.
Each test is self-contained (no cross-test state dependency).
"""
import pytest
from app.services.auth_service import create_user
from app.models.user import UserRole


def test_login_invalid_credentials(client):
    resp = client.post("/api/v1/auth/login", json={"email": "bad@test.com", "password": "wrongpass"})
    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


def test_login_success_and_refresh(client, db_session):
    # Create a user first (use auth_service directly)
    create_user(db_session, "test@example.com", "SecurePass1!", UserRole.admin)
    db_session.flush()

    # Login
    resp = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "SecurePass1!"})
    assert resp.status_code == 200
    tokens = resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # Refresh
    resp2 = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp2.status_code == 200
    assert "access_token" in resp2.json()


def test_operator_cannot_access_admin_only_endpoint(client, db_session):
    """Verify AUTH-05: Operator gets 403 on admin-only endpoint."""
    # Create operator user
    create_user(db_session, "operator@test.com", "OperatorPass1!", UserRole.operator)
    db_session.flush()

    # Login as operator
    op_resp = client.post("/api/v1/auth/login", json={"email": "operator@test.com", "password": "OperatorPass1!"})
    assert op_resp.status_code == 200
    op_token = op_resp.json()["access_token"]

    # Operator cannot access admin-only endpoint (AUTH-05)
    resp = client.get("/api/v1/auth/admin-only", headers={"Authorization": f"Bearer {op_token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_FORBIDDEN"


def test_admin_can_access_admin_only_endpoint(client, db_session):
    """Verify AUTH-03: Admin can access admin-only endpoints."""
    create_user(db_session, "admin2@test.com", "AdminPass2!", UserRole.admin)
    db_session.flush()

    admin_resp = client.post("/api/v1/auth/login", json={"email": "admin2@test.com", "password": "AdminPass2!"})
    admin_token = admin_resp.json()["access_token"]

    resp = client.get("/api/v1/auth/admin-only", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200


def test_invalid_token_returns_structured_error(client):
    """Verify error format: auth errors return proper error code, not stringified dict."""
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401
    # Error should be structured, not a stringified dict
    data = resp.json()
    assert "error" in data
    assert isinstance(data["error"]["code"], str)
    assert not data["error"]["code"].startswith("{")  # Not a stringified dict
