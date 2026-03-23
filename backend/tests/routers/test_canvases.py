"""Unit tests for Canvas CRUD routes.

Uses in-memory SQLite with function-scoped setup/teardown.
Auth is bypassed by overriding get_current_user with a mock admin user.
"""

import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.main import app as fastapi_app
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.base import Base

# Import all models so Base.metadata is fully populated before create_all
from app.models import connector_endpoint as _ce_mod  # noqa: F401
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint  # noqa: F401
from app.models.canvas import Canvas  # noqa: F401
from app.models.canvas_endpoint import CanvasEndpoint  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
from app.models.run_history import RunHistory, RunFailure  # noqa: F401
from app.models.field_mapping import FieldMapping  # noqa: F401
from app.models.qualys_config import QualysConfig  # noqa: F401

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


class _MockAdminUser:
    """Minimal user object that satisfies require_role role check."""
    role = UserRole.admin
    id = "mock-admin-id"
    email = "admin@test.local"
    is_active = True


@pytest.fixture(autouse=True)
def setup_db():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        return _MockAdminUser()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_current_user] = override_get_current_user

    yield TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    fastapi_app.dependency_overrides.clear()


def _seed_connector(session_factory) -> str:
    """Insert a Connector row directly and return its ID."""
    conn_id = str(uuid.uuid4())
    db = session_factory()
    try:
        connector = Connector(
            id=conn_id,
            name="Test Connector",
            base_url="https://api.example.com",
            auth_method="bearer_token",
        )
        db.add(connector)
        db.commit()
    finally:
        db.close()
    return conn_id


def test_create_canvas_success(setup_db):
    """POST /connectors/{id}/canvases with valid payload returns 201."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        resp = client.post(
            f"/api/v1/connectors/{conn_id}/canvases",
            json={"name": "Host Assets", "description": "Main host canvas"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Host Assets"
    assert data["description"] == "Main host canvas"
    assert data["connector_id"] == conn_id
    assert data["is_enabled"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_canvas_connector_not_found(setup_db):
    """POST to non-existent connector returns 404 CONNECTOR_NOT_FOUND."""
    with TestClient(fastapi_app) as client:
        resp = client.post(
            "/api/v1/connectors/does-not-exist/canvases",
            json={"name": "Ghost Canvas"},
        )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CONNECTOR_NOT_FOUND"


def test_list_canvases(setup_db):
    """GET /connectors/{id}/canvases returns list of canvases for that connector."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        # Create two canvases
        client.post(
            f"/api/v1/connectors/{conn_id}/canvases",
            json={"name": "Beta Canvas"},
        )
        client.post(
            f"/api/v1/connectors/{conn_id}/canvases",
            json={"name": "Alpha Canvas"},
        )
        resp = client.get(f"/api/v1/connectors/{conn_id}/canvases")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    # Ordered by name asc
    assert items[0]["name"] == "Alpha Canvas"
    assert items[1]["name"] == "Beta Canvas"


def test_get_canvas_success(setup_db):
    """GET /connectors/{id}/canvases/{canvas_id} returns single canvas."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        create_resp = client.post(
            f"/api/v1/connectors/{conn_id}/canvases",
            json={"name": "Single Canvas", "description": "Test desc"},
        )
        canvas_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/connectors/{conn_id}/canvases/{canvas_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == canvas_id
    assert data["name"] == "Single Canvas"
    assert data["description"] == "Test desc"


def test_get_canvas_not_found(setup_db):
    """GET with non-existent canvas_id returns 404 CANVAS_NOT_FOUND."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        resp = client.get(f"/api/v1/connectors/{conn_id}/canvases/nonexistent-id")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CANVAS_NOT_FOUND"


def test_update_canvas(setup_db):
    """PATCH /connectors/{id}/canvases/{canvas_id} updates only provided fields."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        create_resp = client.post(
            f"/api/v1/connectors/{conn_id}/canvases",
            json={"name": "Original Name", "description": "Original desc", "is_enabled": True},
        )
        canvas_id = create_resp.json()["id"]

        # Update name only
        patch_resp = client.patch(
            f"/api/v1/connectors/{conn_id}/canvases/{canvas_id}",
            json={"name": "Updated Name"},
        )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Original desc"  # unchanged
    assert data["is_enabled"] is True  # unchanged


def test_delete_canvas_returns_204(setup_db):
    """DELETE /connectors/{id}/canvases/{canvas_id} returns 204."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        create_resp = client.post(
            f"/api/v1/connectors/{conn_id}/canvases",
            json={"name": "To Delete"},
        )
        canvas_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/connectors/{conn_id}/canvases/{canvas_id}")
    assert del_resp.status_code == 204


def test_delete_canvas_then_get_returns_404(setup_db):
    """After DELETE, GET for the same canvas returns 404."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        create_resp = client.post(
            f"/api/v1/connectors/{conn_id}/canvases",
            json={"name": "Delete Then Get"},
        )
        canvas_id = create_resp.json()["id"]

        client.delete(f"/api/v1/connectors/{conn_id}/canvases/{canvas_id}")

        get_resp = client.get(f"/api/v1/connectors/{conn_id}/canvases/{canvas_id}")
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "CANVAS_NOT_FOUND"
