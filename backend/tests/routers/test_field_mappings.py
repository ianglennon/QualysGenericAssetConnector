"""Tests for field mapping routes: deprecated 410 responses and is_valid_mappings correctness.

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
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.user import User, UserRole
from app.models.run_history import RunHistory, RunFailure
from app.models.field_mapping import FieldMapping
from app.models.qualys_config import QualysConfig

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
            name="Field Mapping Test Connector",
            base_url="https://fm-test.example.com",
            auth_method="bearer_token",
        )
        db.add(connector)
        db.commit()
    finally:
        db.close()
    return conn_id


def _seed_endpoint(session_factory, connector_id: str) -> str:
    """Insert a ConnectorEndpoint row and return its ID."""
    ep_id = str(uuid.uuid4())
    db = session_factory()
    try:
        endpoint = ConnectorEndpoint(
            id=ep_id,
            connector_id=connector_id,
            name="Test Endpoint",
            path="/devices",
            is_enabled=True,
            display_order=0,
        )
        db.add(endpoint)
        db.commit()
    finally:
        db.close()
    return ep_id


# ---------------------------------------------------------------------------
# Deprecated route tests
# ---------------------------------------------------------------------------

def test_deprecated_create_mapping_returns_410(setup_db):
    """POST /connectors/{id}/mappings should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
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


def test_deprecated_list_mappings_returns_410(setup_db):
    """GET /connectors/{id}/mappings should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        resp = client.get(f"/api/v1/connectors/{conn_id}/mappings")
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_batch_replace_mappings_returns_410(setup_db):
    """PUT /connectors/{id}/mappings should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        resp = client.put(
            f"/api/v1/connectors/{conn_id}/mappings",
            json={"mappings": []},
        )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_update_mapping_returns_410(setup_db):
    """PATCH /connectors/{id}/mappings/{mid} should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(setup_db)
    fake_id = str(uuid.uuid4())
    with TestClient(fastapi_app) as client:
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


def test_deprecated_delete_mapping_returns_410(setup_db):
    """DELETE /connectors/{id}/mappings/{mid} should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(setup_db)
    fake_id = str(uuid.uuid4())
    with TestClient(fastapi_app) as client:
        resp = client.delete(f"/api/v1/connectors/{conn_id}/mappings/{fake_id}")
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


def test_deprecated_preview_mapping_returns_410(setup_db):
    """POST /connectors/{id}/mappings/preview should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        resp = client.post(
            f"/api/v1/connectors/{conn_id}/mappings/preview",
            json={},
        )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"


# ---------------------------------------------------------------------------
# is_valid_mappings correctness test
# ---------------------------------------------------------------------------

def test_batch_replace_endpoint_mappings_returns_actual_is_valid(setup_db):
    """PUT /connectors/{id}/endpoints/{eid}/mappings returns is_valid_mappings reflecting
    actual validation state — not a hardcoded False.

    Step 1: Save empty mappings → no identity attribute → is_valid_mappings must be False.
    Step 2: Save a mapping with target_field=hostName (an identity attribute) → is_valid_mappings must be True.
    """
    conn_id = _seed_connector(setup_db)
    ep_id = _seed_endpoint(setup_db, conn_id)

    with TestClient(fastapi_app) as client:
        # Step 1: Empty mappings → endpoint has no identity attribute → invalid
        resp_empty = client.put(
            f"/api/v1/connectors/{conn_id}/endpoints/{ep_id}/mappings",
            json={"mappings": []},
        )
        assert resp_empty.status_code == 200
        data_empty = resp_empty.json()
        assert data_empty["is_valid_mappings"] is False, (
            f"Expected False for empty mappings but got {data_empty['is_valid_mappings']}"
        )

        # Step 2: Save mapping with identity target_field → valid
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

def test_batch_replace_persists_is_valid_mappings_to_connector(setup_db):
    """batch_replace_endpoint_mappings must write is_valid_mappings to the Connector row.

    Step 1: PUT valid mappings (identity hostName) → response is_valid_mappings=True,
            AND querying Connector row directly shows is_valid_mappings=True.
    Step 2: PUT empty mappings → response is_valid_mappings=False,
            AND querying Connector row directly shows is_valid_mappings=False.
    """
    conn_id = _seed_connector(setup_db)
    ep_id = _seed_endpoint(setup_db, conn_id)

    with TestClient(fastapi_app) as client:
        # Step 1: identity mapping → valid
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

    # Verify DB state (new session to avoid cache)
    db = setup_db()
    try:
        connector = db.query(Connector).filter_by(id=conn_id).first()
        assert connector is not None
        assert connector.is_valid_mappings == True, (
            f"Expected Connector.is_valid_mappings=True in DB after valid PUT, got {connector.is_valid_mappings}"
        )
    finally:
        db.close()

    with TestClient(fastapi_app) as client:
        # Step 2: empty mappings → invalid
        resp = client.put(
            f"/api/v1/connectors/{conn_id}/endpoints/{ep_id}/mappings",
            json={"mappings": []},
        )
        assert resp.status_code == 200
        assert resp.json()["is_valid_mappings"] is False

    # Verify DB state (new session)
    db = setup_db()
    try:
        connector = db.query(Connector).filter_by(id=conn_id).first()
        assert connector is not None
        assert connector.is_valid_mappings == False, (
            f"Expected Connector.is_valid_mappings=False in DB after empty PUT, got {connector.is_valid_mappings}"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Deprecated connector-scoped discover route test
# ---------------------------------------------------------------------------

def test_deprecated_discover_fields_returns_410(setup_db):
    """GET /connectors/{id}/fields/discover should return 410 Gone with ROUTE_DEPRECATED error code."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        resp = client.get(f"/api/v1/connectors/{conn_id}/fields/discover")
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "ROUTE_DEPRECATED"
