"""Tests for field mapping routes: deprecated 410 responses and is_valid_mappings correctness.

Auth is bypassed by overriding get_current_user with a mock admin user.
Uses shared conftest.py fixtures for DB and client.
"""

import uuid

import pytest

from app.core.security import get_current_user
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.user import UserRole


class _MockAdminUser:
    """Minimal user object that satisfies require_role role check."""
    role = UserRole.admin
    id = "mock-admin-id"
    email = "admin@test.local"
    is_active = True


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
        name="Field Mapping Test Connector",
        base_url="https://fm-test.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    db_session.flush()
    return conn_id


def _seed_endpoint(db_session, connector_id: str) -> str:
    """Insert a ConnectorEndpoint row and return its ID."""
    ep_id = str(uuid.uuid4())
    endpoint = ConnectorEndpoint(
        id=ep_id,
        connector_id=connector_id,
        name="Test Endpoint",
        path="/devices",
        is_enabled=True,
        display_order=0,
    )
    db_session.add(endpoint)
    db_session.flush()
    return ep_id


# ---------------------------------------------------------------------------
# Deprecated route tests
# ---------------------------------------------------------------------------

def test_deprecated_create_mapping_returns_410(client, db_session):
    """POST /connectors/{id}/mappings should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(db_session)
    resp = client.post(
        f"/api/v1/connectors/{conn_id}/mappings",
        json={
            "mapping_type": "direct_copy",
            "target_field": "hostName",
            "source_field": "name",
        },
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_list_mappings_returns_410(client, db_session):
    """GET /connectors/{id}/mappings should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(db_session)
    resp = client.get(f"/api/v1/connectors/{conn_id}/mappings")
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_batch_replace_mappings_returns_410(client, db_session):
    """PUT /connectors/{id}/mappings should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(db_session)
    resp = client.put(
        f"/api/v1/connectors/{conn_id}/mappings",
        json={"mappings": []},
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_update_mapping_returns_410(client, db_session):
    """PATCH /connectors/{id}/mappings/{mid} should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(db_session)
    fake_id = str(uuid.uuid4())
    resp = client.patch(
        f"/api/v1/connectors/{conn_id}/mappings/{fake_id}",
        json={
            "mapping_type": "direct_copy",
            "target_field": "hostName",
            "source_field": "name",
        },
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_delete_mapping_returns_410(client, db_session):
    """DELETE /connectors/{id}/mappings/{mid} should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(db_session)
    fake_id = str(uuid.uuid4())
    resp = client.delete(f"/api/v1/connectors/{conn_id}/mappings/{fake_id}")
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_preview_mapping_returns_410(client, db_session):
    """POST /connectors/{id}/mappings/preview should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(db_session)
    resp = client.post(
        f"/api/v1/connectors/{conn_id}/mappings/preview",
        json={},
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


# ---------------------------------------------------------------------------
# is_valid_mappings correctness test
# ---------------------------------------------------------------------------

def test_batch_replace_endpoint_mappings_returns_actual_is_valid(client, db_session):
    """PUT /connectors/{id}/endpoints/{eid}/mappings returns is_valid_mappings reflecting
    actual validation state -- not a hardcoded False.

    Step 1: Save empty mappings -> no identity attribute -> is_valid_mappings must be False.
    Step 2: Save a mapping with target_field=hostName (an identity attribute) -> is_valid_mappings must be True.
    """
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)

    # Step 1: Empty mappings -> endpoint has no identity attribute -> invalid
    resp_empty = client.put(
        f"/api/v1/connectors/{conn_id}/endpoints/{ep_id}/mappings",
        json={"mappings": []},
    )
    assert resp_empty.status_code == 200
    data_empty = resp_empty.json()
    assert data_empty["is_valid_mappings"] is False, (
        f"Expected False for empty mappings but got {data_empty['is_valid_mappings']}"
    )

    # Step 2: Save mapping with identity target_field -> valid
    resp_valid = client.put(
        f"/api/v1/connectors/{conn_id}/endpoints/{ep_id}/mappings",
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


# ---------------------------------------------------------------------------
# DB persistence of is_valid_mappings
# ---------------------------------------------------------------------------

def test_batch_replace_persists_is_valid_mappings_to_connector(client, db_session):
    """batch_replace_endpoint_mappings must write is_valid_mappings to the Connector row.

    Step 1: PUT valid mappings (identity hostName) -> response is_valid_mappings=True,
            AND querying Connector row directly shows is_valid_mappings=True.
    Step 2: PUT empty mappings -> response is_valid_mappings=False,
            AND querying Connector row directly shows is_valid_mappings=False.
    """
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)

    # Step 1: identity mapping -> valid
    resp = client.put(
        f"/api/v1/connectors/{conn_id}/endpoints/{ep_id}/mappings",
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
    assert resp.status_code == 200
    assert resp.json()["is_valid_mappings"] is True

    # Verify DB state -- expire to pick up changes from the app's session
    db_session.expire_all()
    connector = db_session.query(Connector).filter_by(id=conn_id).first()
    assert connector is not None
    assert connector.is_valid_mappings == True, (
        f"Expected Connector.is_valid_mappings=True in DB after valid PUT, got {connector.is_valid_mappings}"
    )

    # Step 2: empty mappings -> invalid
    resp = client.put(
        f"/api/v1/connectors/{conn_id}/endpoints/{ep_id}/mappings",
        json={"mappings": []},
    )
    assert resp.status_code == 200
    assert resp.json()["is_valid_mappings"] is False

    # Verify DB state
    db_session.expire_all()
    connector = db_session.query(Connector).filter_by(id=conn_id).first()
    assert connector is not None
    assert connector.is_valid_mappings == False, (
        f"Expected Connector.is_valid_mappings=False in DB after empty PUT, got {connector.is_valid_mappings}"
    )


# ---------------------------------------------------------------------------
# Deprecated connector-scoped discover route test
# ---------------------------------------------------------------------------

def test_deprecated_discover_fields_returns_410(client, db_session):
    """GET /connectors/{id}/fields/discover should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(db_session)
    resp = client.get(f"/api/v1/connectors/{conn_id}/fields/discover")
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"
