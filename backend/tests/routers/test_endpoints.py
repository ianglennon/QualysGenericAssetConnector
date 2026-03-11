"""Unit tests for ConnectorEndpoint CRUD routes.

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


def test_list_endpoints_empty(setup_db):
    """GET returns empty list for connector with no endpoints."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        resp = client.get(f"/api/v1/connectors/{conn_id}/endpoints")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_and_list_endpoint(setup_db):
    """POST creates endpoint; GET list returns it ordered by display_order."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
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


def test_patch_updates_only_provided_fields(setup_db):
    """PATCH updates is_enabled and name without touching other fields."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
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


def test_delete_returns_204_and_removes_endpoint(setup_db):
    """DELETE returns 204 and subsequent GET list is empty."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        create_resp = client.post(
            f"/api/v1/connectors/{conn_id}/endpoints",
            json={"name": "ToDelete", "path": "/delete-me"},
        )
        ep_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/connectors/{conn_id}/endpoints/{ep_id}")
        assert del_resp.status_code == 204

        list_resp = client.get(f"/api/v1/connectors/{conn_id}/endpoints")
        assert list_resp.json() == []


def test_reorder_updates_display_order(setup_db):
    """POST /reorder updates display_order values correctly."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
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


def test_get_single_endpoint_404_for_unknown(setup_db):
    """GET single endpoint returns 404 for unknown ID."""
    conn_id = _seed_connector(setup_db)
    with TestClient(fastapi_app) as client:
        resp = client.get(f"/api/v1/connectors/{conn_id}/endpoints/nonexistent-id")
    assert resp.status_code == 404


def test_create_endpoint_404_for_unknown_connector(setup_db):
    """POST to non-existent connector returns 404."""
    with TestClient(fastapi_app) as client:
        resp = client.post(
            "/api/v1/connectors/does-not-exist/endpoints",
            json={"name": "X", "path": "/x"},
        )
    assert resp.status_code == 404
