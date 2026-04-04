"""Tests for authentication endpoints.

Uses shared conftest.py fixtures for DB and client.
Each test is self-contained (no cross-test state dependency).
"""
import pytest
from app.services.auth_service import create_user


def test_login_invalid_credentials(client):
    resp = client.post("/api/v1/auth/login", json={"email": "bad@test.com", "password": "wrongpass"})
    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


def test_login_success_and_refresh(client, db_session, admin_role):
    # Create a user first (use auth_service directly)
    create_user(db_session, "test@example.com", "SecurePass12!", role_id=admin_role.id)
    db_session.flush()

    # Login
    resp = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "SecurePass12!"})
    assert resp.status_code == 200
    tokens = resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # Refresh
    resp2 = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp2.status_code == 200
    assert "access_token" in resp2.json()


def test_operator_cannot_access_admin_only_endpoint(client, db_session, operator_role):
    """Verify AUTH-05: Operator gets 403 on admin-only endpoint."""
    # Create operator user
    create_user(db_session, "operator@test.com", "OperatorPass12!", role_id=operator_role.id)
    db_session.flush()

    # Login as operator
    op_resp = client.post("/api/v1/auth/login", json={"email": "operator@test.com", "password": "OperatorPass12!"})
    assert op_resp.status_code == 200
    op_token = op_resp.json()["access_token"]

    # Operator cannot access admin-only endpoint (AUTH-05)
    resp = client.get("/api/v1/auth/admin-only", headers={"Authorization": f"Bearer {op_token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_FORBIDDEN"


def test_admin_can_access_admin_only_endpoint(client, db_session, admin_role):
    """Verify AUTH-03: Admin can access admin-only endpoints."""
    create_user(db_session, "admin2@test.com", "AdminPass22!", role_id=admin_role.id)
    db_session.flush()

    admin_resp = client.post("/api/v1/auth/login", json={"email": "admin2@test.com", "password": "AdminPass22!"})
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


def test_me_returns_role_with_permissions(client, db_session, admin_role):
    """PERM-02: /auth/me returns role object with permissions array."""
    create_user(db_session, "me_test@test.com", "MeTestPass12!!", role_id=admin_role.id)
    db_session.flush()
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "me_test@test.com", "password": "MeTestPass12!!"
    })
    token = login_resp.json()["access_token"]
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert "role" in data
    assert "id" in data["role"]
    assert data["role"]["name"] == "Administrator"
    assert data["role"]["is_system"] is True
    assert "permissions" in data["role"]
    assert "connectors:create" in data["role"]["permissions"]
    assert len(data["role"]["permissions"]) == 30


def test_jwt_contains_permissions(client, db_session, admin_role):
    """PERM-02: JWT tokens contain permissions array."""
    import jwt as pyjwt
    from app.core.settings import get_settings
    create_user(db_session, "jwt_test@test.com", "JwtTestPass12!!", role_id=admin_role.id)
    db_session.flush()
    resp = client.post("/api/v1/auth/login", json={
        "email": "jwt_test@test.com", "password": "JwtTestPass12!!"
    })
    token = resp.json()["access_token"]
    settings = get_settings()
    payload = pyjwt.decode(token, settings.secret_key, algorithms=["HS256"])
    assert "permissions" in payload
    assert isinstance(payload["permissions"], list)
    assert len(payload["permissions"]) == 30
    assert "connectors:create" in payload["permissions"]
    assert payload["role"] == "Administrator"
