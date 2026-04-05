"""Tests for Qualys config endpoints.

Uses shared conftest.py fixtures for DB and client.
"""
import pytest


def test_put_qualys_config_as_admin(client, admin_token):
    resp = client.put(
        "/api/v1/qualys/config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "quays2ab1", "password": "testpass123", "connector_uuid": "abc-123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "quays2ab1"
    assert data["connector_uuid"] == "abc-123"
    assert data["has_password"] is True
    assert "password" not in data
    assert "encrypted_password" not in data
    assert "api_url" not in data
    assert "has_token" not in data


def test_put_qualys_config_invalid_username(client, admin_token):
    resp = client.put(
        "/api/v1/qualys/config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "invaliduser", "password": "testpass123", "connector_uuid": "abc-123"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "QUALYS_INVALID_USERNAME"


def test_put_qualys_config_missing_fields(client, admin_token):
    # Missing password and connector_uuid
    resp = client.put(
        "/api/v1/qualys/config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "quays2ab1"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_qualys_config_never_returns_secrets(client, admin_token):
    # Ensure config exists first
    client.put(
        "/api/v1/qualys/config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "quays2ab1", "password": "testpass123", "connector_uuid": "abc-123"},
    )
    resp = client.get("/api/v1/qualys/config", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    # Verify correct fields present
    assert "id" in data
    assert "username" in data
    assert "connector_uuid" in data
    assert "has_password" in data
    # Verify removed/secret fields absent
    for forbidden_key in ("password", "token", "encrypted_password", "encrypted_token", "api_url", "has_token"):
        assert forbidden_key not in data


def test_get_qualys_config_includes_platform_fields(client, admin_token):
    # Ensure config exists first
    client.put(
        "/api/v1/qualys/config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "quays2ab1", "password": "testpass123", "connector_uuid": "abc-123"},
    )
    resp = client.get("/api/v1/qualys/config", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    # Verify platform fields are present and non-empty
    assert "platform_name" in data
    assert "api_server_url" in data
    assert "api_gateway_url" in data
    assert isinstance(data["platform_name"], str) and len(data["platform_name"]) > 0
    assert data["api_server_url"].startswith("https://")
    assert data["api_gateway_url"].startswith("https://")


def test_user_without_settings_read_cannot_access_qualys_config(client, db_session):
    """A user without settings:read permission gets 403 on qualys config."""
    from app.models.role import Role, RolePermission
    from app.services.auth_service import create_user

    # Create a role with only runs:read (no settings:read)
    role = Role(name="NoSettingsRole", description="No settings access", is_system=False)
    db_session.add(role)
    db_session.flush()
    db_session.add(RolePermission(role_id=role.id, permission="runs:read"))
    db_session.flush()

    create_user(db_session, "nosettings@test.com", "NoSettingsPass12!!", role_id=role.id)
    db_session.flush()
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "nosettings@test.com",
        "password": "NoSettingsPass12!!"
    })
    token = login_resp.json()["access_token"]

    resp = client.get("/api/v1/qualys/config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_FORBIDDEN"
