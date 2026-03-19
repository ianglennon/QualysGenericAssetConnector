import pytest
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from app.main import create_app
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.services.auth_service import create_user
from app.models.user import UserRole


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    app = create_app()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def admin_token(client):
    db = SessionLocal()
    create_user(db, "qualys_admin@test.com", "AdminPass12!!", UserRole.admin)
    db.close()
    resp = client.post("/api/v1/auth/login", json={"email": "qualys_admin@test.com", "password": "AdminPass12!!"})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def operator_token(client):
    db = SessionLocal()
    create_user(db, "qualys_op@test.com", "OperatorPass12!!", UserRole.operator)
    db.close()
    resp = client.post("/api/v1/auth/login", json={"email": "qualys_op@test.com", "password": "OperatorPass12!!"})
    return resp.json()["access_token"]


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


def test_operator_cannot_access_qualys_config(client, operator_token):
    resp = client.get("/api/v1/qualys/config", headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_FORBIDDEN"
