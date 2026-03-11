"""Tests for field mapping routes: deprecated 410 responses and is_valid_mappings correctness."""

import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_field_mappings.db")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.main import create_app
from app.db.session import SessionLocal
from app.services.auth_service import create_user
from app.models.user import UserRole


@pytest.fixture(scope="module")
def client():
    db_path = os.path.abspath("test_field_mappings.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    app = create_app()
    with TestClient(app) as c:
        yield c
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="module")
def admin_token(client):
    db = SessionLocal()
    create_user(db, "fm_admin@test.com", "AdminPass12!", UserRole.admin)
    db.close()
    resp = client.post("/api/v1/auth/login", json={"email": "fm_admin@test.com", "password": "AdminPass12!"})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def connector_id(client, admin_token):
    """Create a test connector and return its ID."""
    resp = client.post(
        "/api/v1/connectors/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Field Mapping Test Connector",
            "base_url": "https://fm-test.example.com",
            "auth_method": "bearer_token",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.fixture(scope="module")
def endpoint_id(client, admin_token, connector_id):
    """Create a test endpoint and return its ID."""
    resp = client.post(
        f"/api/v1/connectors/{connector_id}/endpoints",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Test Endpoint", "path": "/devices", "is_enabled": True},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Deprecated route tests (RED phase — these FAIL before Task 2 implementation)
# ---------------------------------------------------------------------------

def test_deprecated_create_mapping_returns_410(client, admin_token, connector_id):
    """POST /connectors/{id}/mappings should return 410 Gone with ROUTE_DEPRECATED error code."""
    resp = client.post(
        f"/api/v1/connectors/{connector_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "mapping_type": "direct_copy",
            "target_field": "hostName",
            "source_field": "name",
        },
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_list_mappings_returns_410(client, admin_token, connector_id):
    """GET /connectors/{id}/mappings should return 410 Gone with ROUTE_DEPRECATED error code."""
    resp = client.get(
        f"/api/v1/connectors/{connector_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_batch_replace_mappings_returns_410(client, admin_token, connector_id):
    """PUT /connectors/{id}/mappings should return 410 Gone with ROUTE_DEPRECATED error code."""
    resp = client.put(
        f"/api/v1/connectors/{connector_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"mappings": []},
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_update_mapping_returns_410(client, admin_token, connector_id):
    """PATCH /connectors/{id}/mappings/{mid} should return 410 Gone with ROUTE_DEPRECATED error code."""
    fake_id = str(uuid.uuid4())
    resp = client.patch(
        f"/api/v1/connectors/{connector_id}/mappings/{fake_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "mapping_type": "direct_copy",
            "target_field": "hostName",
            "source_field": "name",
        },
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_delete_mapping_returns_410(client, admin_token, connector_id):
    """DELETE /connectors/{id}/mappings/{mid} should return 410 Gone with ROUTE_DEPRECATED error code."""
    fake_id = str(uuid.uuid4())
    resp = client.delete(
        f"/api/v1/connectors/{connector_id}/mappings/{fake_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_preview_mapping_returns_410(client, admin_token, connector_id):
    """POST /connectors/{id}/mappings/preview should return 410 Gone with ROUTE_DEPRECATED error code."""
    resp = client.post(
        f"/api/v1/connectors/{connector_id}/mappings/preview",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={},
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


# ---------------------------------------------------------------------------
# is_valid_mappings correctness test
# ---------------------------------------------------------------------------

def test_batch_replace_endpoint_mappings_returns_actual_is_valid(client, admin_token, connector_id, endpoint_id):
    """PUT /connectors/{id}/endpoints/{eid}/mappings returns is_valid_mappings reflecting
    actual validation state — not a hardcoded False.

    Step 1: Save empty mappings → no identity attribute → is_valid_mappings must be False.
    Step 2: Save a mapping with target_field=hostName (an identity attribute) → is_valid_mappings must be True.
    """
    # Step 1: Empty mappings → endpoint has no identity attribute → invalid
    resp_empty = client.put(
        f"/api/v1/connectors/{connector_id}/endpoints/{endpoint_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"mappings": []},
    )
    assert resp_empty.status_code == 200
    data_empty = resp_empty.json()
    assert data_empty["is_valid_mappings"] is False, (
        f"Expected False for empty mappings but got {data_empty['is_valid_mappings']}"
    )

    # Step 2: Save mapping with identity target_field → valid
    resp_valid = client.put(
        f"/api/v1/connectors/{connector_id}/endpoints/{endpoint_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "mappings": [
                {
                    "mapping_type": "direct_copy",
                    "target_field": "hostName",
                    "source_field": "name",
                    "order": 0,
                }
            ]
        },
    )
    assert resp_valid.status_code == 200
    data_valid = resp_valid.json()
    assert data_valid["is_valid_mappings"] is True, (
        f"Expected True for identity mapping but got {data_valid['is_valid_mappings']}"
    )
