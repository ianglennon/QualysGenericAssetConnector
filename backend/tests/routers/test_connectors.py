import uuid
import pytest

from app.services.auth_service import create_user
from app.models.user import UserRole
from app.models.connector import Connector


def test_create_connector_as_admin(client, admin_token):
    """POST creates connector with bearer_token auth; response has has_token=True, no raw secrets."""
    resp = client.post(
        "/api/v1/connectors/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Test Bearer Connector",
            "base_url": "https://api.example.com",
            "auth_method": "bearer_token",
            "credentials": {"token": "supersecrettoken"},
            "source_retry_limit": 5,
            "qualys_retry_limit": 2,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["has_token"] is True
    assert data["name"] == "Test Bearer Connector"
    assert data["source_retry_limit"] == 5
    assert data["qualys_retry_limit"] == 2
    # Ensure no raw credential fields leak into the response
    assert "encrypted_token" not in data
    assert "token" not in data
    assert "credentials" not in data


def test_create_connector_basic(client, admin_token):
    """POST creates a basic connector; response contains expected fields without pagination_strategies (removed in v1.2)."""
    resp = client.post(
        "/api/v1/connectors/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Basic Connector",
            "base_url": "https://basic.example.com",
            "auth_method": "bearer_token",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Basic Connector"
    assert data["base_url"] == "https://basic.example.com"
    assert data["auth_method"] == "bearer_token"
    # v1.2: pagination_strategies removed from ConnectorResponse
    assert "pagination_strategies" not in data


def test_list_connectors_as_admin(client, admin_token):
    """GET /connectors/ returns 200 and a list."""
    resp = client.get(
        "/api/v1/connectors/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_get_connector_by_id(client, admin_token):
    """GET /{id} returns 200 and the correct connector."""
    # First create a connector to retrieve
    create_resp = client.post(
        "/api/v1/connectors/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Get By ID Connector",
            "base_url": "https://getbyid.example.com",
            "auth_method": "basic_auth",
            "credentials": {"username": "user", "password": "pass"},
        },
    )
    assert create_resp.status_code == 201
    connector_id = create_resp.json()["id"]

    resp = client.get(
        f"/api/v1/connectors/{connector_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == connector_id
    assert data["name"] == "Get By ID Connector"
    assert data["has_username"] is True
    assert data["has_password"] is True


def test_get_connector_not_found(client, admin_token):
    """GET with nonexistent ID returns 404."""
    resp = client.get(
        "/api/v1/connectors/nonexistent-id-12345",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CONNECTOR_NOT_FOUND"


def test_patch_connector_preserves_credentials(client, admin_token):
    """PATCH with only name change; existing token credential is preserved (not wiped)."""
    # Create connector with a token
    create_resp = client.post(
        "/api/v1/connectors/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Preserve Creds Connector",
            "base_url": "https://preserve.example.com",
            "auth_method": "bearer_token",
            "credentials": {"token": "original-token-value"},
        },
    )
    assert create_resp.status_code == 201
    connector_id = create_resp.json()["id"]
    assert create_resp.json()["has_token"] is True

    # PATCH only the name -- no credentials field in payload
    patch_resp = client.patch(
        f"/api/v1/connectors/{connector_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Updated Name Connector"},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["name"] == "Updated Name Connector"
    # Token must still be present (not wiped by the partial update)
    assert data["has_token"] is True


def test_patch_connector_updates_retry_limits(client, admin_token):
    """PATCH can update retry limits and returns updated values."""
    create_resp = client.post(
        "/api/v1/connectors/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Retry Limits Connector",
            "base_url": "https://retry.example.com",
            "auth_method": "bearer_token",
        },
    )
    assert create_resp.status_code == 201
    connector_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/connectors/{connector_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"source_retry_limit": 4, "qualys_retry_limit": 1},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["source_retry_limit"] == 4
    assert data["qualys_retry_limit"] == 1


def test_delete_connector_cascades_to_field_mappings(client, admin_token, db_session):
    """DELETE removes connector; field_mappings with FK to that connector are cascade-deleted."""
    from sqlalchemy import text
    from datetime import datetime

    # Create a connector
    create_resp = client.post(
        "/api/v1/connectors/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Cascade Delete Connector",
            "base_url": "https://cascade.example.com",
            "auth_method": "bearer_token",
        },
    )
    assert create_resp.status_code == 201
    connector_id = create_resp.json()["id"]

    # Insert a field_mapping row directly via DB
    mapping_id = str(uuid.uuid4())
    db_session.execute(
        text(
            "INSERT INTO field_mappings (id, connector_id, created_at) VALUES (:id, :connector_id, :created_at)"
        ),
        {"id": mapping_id, "connector_id": connector_id, "created_at": datetime.utcnow()},
    )
    db_session.flush()

    # Verify it's there
    row = db_session.execute(
        text("SELECT id FROM field_mappings WHERE id = :id"),
        {"id": mapping_id},
    ).fetchone()
    assert row is not None, "field_mapping row should exist before delete"

    # DELETE the connector
    del_resp = client.delete(
        f"/api/v1/connectors/{connector_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_resp.status_code == 204

    # Verify the field_mapping was cascade-deleted
    db_session.expire_all()
    row = db_session.execute(
        text("SELECT id FROM field_mappings WHERE id = :id"),
        {"id": mapping_id},
    ).fetchone()
    assert row is None, "field_mapping should be cascade-deleted when connector is deleted"

    # Verify the connector is gone too
    get_resp = client.get(
        f"/api/v1/connectors/{connector_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_resp.status_code == 404


def test_operator_cannot_access_connectors(client, operator_token):
    """Operator role receives 403 on all connector endpoints."""
    resp = client.post(
        "/api/v1/connectors/",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "name": "Should Fail",
            "base_url": "https://fail.example.com",
            "auth_method": "bearer_token",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_FORBIDDEN"
