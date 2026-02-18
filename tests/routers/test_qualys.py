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
    create_user(db, "qualys_admin@test.com", "AdminPass1!", UserRole.admin)
    db.close()
    resp = client.post("/api/v1/auth/login", json={"email": "qualys_admin@test.com", "password": "AdminPass1!"})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def operator_token(client):
    db = SessionLocal()
    create_user(db, "qualys_op@test.com", "OperatorPass1!", UserRole.operator)
    db.close()
    resp = client.post("/api/v1/auth/login", json={"email": "qualys_op@test.com", "password": "OperatorPass1!"})
    return resp.json()["access_token"]


def test_put_qualys_config_as_admin(client, admin_token):
    resp = client.put(
        "/api/v1/qualys/config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"api_url": "https://qualysapi.qg2.apps.qualys.com", "username": "testuser", "password": "testpass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["api_url"] == "https://qualysapi.qg2.apps.qualys.com"
    assert data["has_password"] is True
    assert "password" not in data
    assert "encrypted_password" not in data


def test_get_qualys_config_never_returns_secrets(client, admin_token):
    resp = client.get("/api/v1/qualys/config", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    # Verify no raw secret fields in response
    for forbidden_key in ("password", "token", "encrypted_password", "encrypted_token"):
        assert forbidden_key not in data


def test_operator_cannot_access_qualys_config(client, operator_token):
    resp = client.get("/api/v1/qualys/config", headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_FORBIDDEN"
