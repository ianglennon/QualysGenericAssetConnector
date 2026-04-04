"""Unit tests for ConnectorEndpoint CRUD routes.

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


def test_list_endpoints_empty(client, db_session):
    """GET returns empty list for connector with no endpoints."""
    conn_id = _seed_connector(db_session)
    resp = client.get(f"/api/v1/connectors/{conn_id}/endpoints")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_and_list_endpoint(client, db_session):
    """POST creates endpoint; GET list returns it ordered by display_order."""
    conn_id = _seed_connector(db_session)
    create_resp = client.post(
        f"/api/v1/connectors/{conn_id}/endpoints",
        json={"name": "Devices", "path": "/devices", "display_order": 0},
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["name"] == "Devices"
    assert data["path"] == "/devices"
    assert data["connector_id"] == conn_id
    assert data["is_enabled"] is True
    assert data["display_order"] == 0

    list_resp = client.get(f"/api/v1/connectors/{conn_id}/endpoints")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Devices"


def test_patch_updates_only_provided_fields(client, db_session):
    """PATCH updates is_enabled and name without touching other fields."""
    conn_id = _seed_connector(db_session)
    create_resp = client.post(
        f"/api/v1/connectors/{conn_id}/endpoints",
        json={"name": "Original", "path": "/orig", "is_enabled": True},
    )
    ep_id = create_resp.json()["id"]

    # Toggle is_enabled only
    patch_resp = client.patch(
        f"/api/v1/connectors/{conn_id}/endpoints/{ep_id}",
        json={"is_enabled": False},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["is_enabled"] is False
    assert data["name"] == "Original"  # unchanged
    assert data["path"] == "/orig"      # unchanged

    # Change name only
    patch_resp2 = client.patch(
        f"/api/v1/connectors/{conn_id}/endpoints/{ep_id}",
        json={"name": "Renamed"},
    )
    assert patch_resp2.status_code == 200
    assert patch_resp2.json()["name"] == "Renamed"
    assert patch_resp2.json()["is_enabled"] is False  # preserved from previous patch


def test_delete_returns_204_and_removes_endpoint(client, db_session):
    """DELETE returns 204 and subsequent GET list is empty."""
    conn_id = _seed_connector(db_session)
    create_resp = client.post(
        f"/api/v1/connectors/{conn_id}/endpoints",
        json={"name": "ToDelete", "path": "/delete-me"},
    )
    ep_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/connectors/{conn_id}/endpoints/{ep_id}")
    assert del_resp.status_code == 204

    list_resp = client.get(f"/api/v1/connectors/{conn_id}/endpoints")
    assert list_resp.json() == []


def test_reorder_updates_display_order(client, db_session):
    """POST /reorder updates display_order values correctly."""
    conn_id = _seed_connector(db_session)
    # Create two endpoints
    ep_a = client.post(
        f"/api/v1/connectors/{conn_id}/endpoints",
        json={"name": "Alpha", "path": "/alpha", "display_order": 0},
    ).json()["id"]
    ep_b = client.post(
        f"/api/v1/connectors/{conn_id}/endpoints",
        json={"name": "Beta", "path": "/beta", "display_order": 1},
    ).json()["id"]

    # Reorder: put Beta first
    reorder_resp = client.post(
        f"/api/v1/connectors/{conn_id}/endpoints/reorder",
        json={"order": [ep_b, ep_a]},
    )
    assert reorder_resp.status_code == 200
    items = reorder_resp.json()
    assert items[0]["id"] == ep_b
    assert items[0]["display_order"] == 0
    assert items[1]["id"] == ep_a
    assert items[1]["display_order"] == 1


def test_get_single_endpoint_404_for_unknown(client, db_session):
    """GET single endpoint returns 404 for unknown ID."""
    conn_id = _seed_connector(db_session)
    resp = client.get(f"/api/v1/connectors/{conn_id}/endpoints/nonexistent-id")
    assert resp.status_code == 404


def test_create_endpoint_404_for_unknown_connector(client, db_session):
    """POST to non-existent connector returns 404."""
    resp = client.post(
        "/api/v1/connectors/does-not-exist/endpoints",
        json={"name": "X", "path": "/x"},
    )
    assert resp.status_code == 404
