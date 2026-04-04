"""Tests for authentication endpoints including password change and must_change_password.

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


def test_operator_permission_enforcement(client, operator_token):
    """Verify PERM-01: Operator gets 403 on endpoints requiring users:read permission."""
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_FORBIDDEN"


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


# --- Password change tests (USER-06) ---


def test_change_password_success(client, db_session, admin_role):
    """POST /auth/change-password with valid current_password + new_password returns new tokens."""
    create_user(db_session, "changepw@test.com", "OldPassWord12!!", role_id=admin_role.id)
    db_session.flush()
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "changepw@test.com", "password": "OldPassWord12!!"
    })
    token = login_resp.json()["access_token"]

    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassWord12!!", "new_password": "NewPassWord99!!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Verify new password works for login
    login2 = client.post("/api/v1/auth/login", json={
        "email": "changepw@test.com", "password": "NewPassWord99!!"
    })
    assert login2.status_code == 200


def test_change_password_wrong_current(client, db_session, admin_role):
    """Wrong current_password returns 401 AUTH_WRONG_PASSWORD."""
    create_user(db_session, "wrongpw@test.com", "OldPassWord12!!", role_id=admin_role.id)
    db_session.flush()
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "wrongpw@test.com", "password": "OldPassWord12!!"
    })
    token = login_resp.json()["access_token"]

    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongOldPassWord12!!", "new_password": "NewPassWord99!!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_WRONG_PASSWORD"


def test_change_password_weak_new(client, db_session, admin_role):
    """New password failing policy returns 422 AUTH_PASSWORD_POLICY."""
    create_user(db_session, "weakpw@test.com", "OldPassWord12!!", role_id=admin_role.id)
    db_session.flush()
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "weakpw@test.com", "password": "OldPassWord12!!"
    })
    token = login_resp.json()["access_token"]

    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassWord12!!", "new_password": "short"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "AUTH_PASSWORD_POLICY"


# --- must_change_password enforcement tests ---


def test_must_change_password_blocks_endpoints(client, db_session, admin_role):
    """User with must_change_password=true gets 403 AUTH_PASSWORD_CHANGE_REQUIRED on non-exempt endpoints."""
    from app.models.user import User
    user = create_user(db_session, "mustchange@test.com", "TempPass12!!", role_id=admin_role.id)
    user.must_change_password = True
    db_session.flush()

    login_resp = client.post("/api/v1/auth/login", json={
        "email": "mustchange@test.com", "password": "TempPass12!!"
    })
    token = login_resp.json()["access_token"]

    # Accessing /users should be blocked
    resp = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_PASSWORD_CHANGE_REQUIRED"


def test_must_change_password_allows_exempt_paths(client, db_session, admin_role):
    """User with must_change_password=true can still access /auth/me and /auth/change-password."""
    user = create_user(db_session, "mustchange2@test.com", "TempPass12!!", role_id=admin_role.id)
    user.must_change_password = True
    db_session.flush()

    login_resp = client.post("/api/v1/auth/login", json={
        "email": "mustchange2@test.com", "password": "TempPass12!!"
    })
    token = login_resp.json()["access_token"]

    # /auth/me should work
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200

    # /auth/change-password should work (not blocked by must_change_password)
    change_resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "TempPass12!!", "new_password": "NewSecurePass99!!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert change_resp.status_code == 200
    # After changing, must_change_password should be cleared
    new_token = change_resp.json()["access_token"]

    # Now accessing /users should work with new token
    users_resp = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert users_resp.status_code == 200
