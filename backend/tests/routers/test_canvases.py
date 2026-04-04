"""Unit tests for Canvas CRUD routes.

Auth is bypassed by overriding get_current_user with a mock admin user.
Uses shared conftest.py fixtures for DB and client.
"""

import uuid

import pytest

from app.core.security import get_current_user
from app.models.connector import Connector
from app.core.permissions import ALL_PERMISSIONS as _ALL_PERMS


class _MockRole:
    name = "Administrator"
    id = "mock-role-id"
    is_system = True


class _MockAdminUser:
    """Minimal user object that satisfies require_role and permission checks."""
    id = "mock-admin-id"
    email = "admin@test.local"
    is_active = True
    permissions = list(_ALL_PERMS)
    role = _MockRole()
    role_id = "mock-role-id"


@pytest.fixture(autouse=True)
def _mock_admin_auth(client):
    """Override get_current_user to bypass auth for these tests."""
    from app.main import app as fastapi_app
    fastapi_app.dependency_overrides[get_current_user] = lambda: _MockAdminUser()
    yield


def _seed_connector(db_session) -> str:
    """Insert a Connector row directly and return its ID."""
    conn_id = str(uuid.uuid4())
    connector = Connector(
        id=conn_id,
        name="Test Connector",
        base_url="https://api.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    db_session.flush()
    return conn_id


def test_create_canvas_success(client, db_session):
    """POST /connectors/{id}/canvases with valid payload returns 201."""
    conn_id = _seed_connector(db_session)
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


def test_create_canvas_connector_not_found(client, db_session):
    """POST to non-existent connector returns 404 CONNECTOR_NOT_FOUND."""
    resp = client.post(
        "/api/v1/connectors/does-not-exist/canvases",
        json={"name": "Ghost Canvas"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CONNECTOR_NOT_FOUND"


def test_list_canvases(client, db_session):
    """GET /connectors/{id}/canvases returns list of canvases for that connector."""
    conn_id = _seed_connector(db_session)
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


def test_get_canvas_success(client, db_session):
    """GET /connectors/{id}/canvases/{canvas_id} returns single canvas."""
    conn_id = _seed_connector(db_session)
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


def test_get_canvas_not_found(client, db_session):
    """GET with non-existent canvas_id returns 404 CANVAS_NOT_FOUND."""
    conn_id = _seed_connector(db_session)
    resp = client.get(f"/api/v1/connectors/{conn_id}/canvases/nonexistent-id")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CANVAS_NOT_FOUND"


def test_update_canvas(client, db_session):
    """PATCH /connectors/{id}/canvases/{canvas_id} updates only provided fields."""
    conn_id = _seed_connector(db_session)
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


def test_delete_canvas_returns_204(client, db_session):
    """DELETE /connectors/{id}/canvases/{canvas_id} returns 204."""
    conn_id = _seed_connector(db_session)
    create_resp = client.post(
        f"/api/v1/connectors/{conn_id}/canvases",
        json={"name": "To Delete"},
    )
    canvas_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/connectors/{conn_id}/canvases/{canvas_id}")
    assert del_resp.status_code == 204


def test_delete_canvas_then_get_returns_404(client, db_session):
    """After DELETE, GET for the same canvas returns 404."""
    conn_id = _seed_connector(db_session)
    create_resp = client.post(
        f"/api/v1/connectors/{conn_id}/canvases",
        json={"name": "Delete Then Get"},
    )
    canvas_id = create_resp.json()["id"]

    client.delete(f"/api/v1/connectors/{conn_id}/canvases/{canvas_id}")

    get_resp = client.get(f"/api/v1/connectors/{conn_id}/canvases/{canvas_id}")
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "CANVAS_NOT_FOUND"
