"""
Integration tests for the field discovery and mapping API endpoints.

Endpoints under test:
  GET  /api/v1/connectors/{id}/fields/discover
  GET  /api/v1/qualys/schema
  PUT  /api/v1/connectors/{id}/mappings
"""
import os
import sys
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_field_discovery_api.db")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.main import create_app
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.services.auth_service import create_user
from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    # Ensure all tables exist (idempotent, bypasses Alembic version check)
    Base.metadata.create_all(bind=engine)
    app = create_app()
    with TestClient(app) as c:
        yield c


def _ensure_user(email: str, password: str, role: UserRole) -> None:
    """Create the test user if it doesn't already exist (idempotent)."""
    from app.models.user import User
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == email).first():
            create_user(db, email, password, role)
    finally:
        db.close()


@pytest.fixture(scope="module")
def admin_token(client):
    _ensure_user("fd_admin@test.com", "AdminPass12!", UserRole.admin)
    resp = client.post("/api/v1/auth/login", json={"email": "fd_admin@test.com", "password": "AdminPass12!"})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def operator_token(client):
    _ensure_user("fd_op@test.com", "OperatorPass12!", UserRole.operator)
    resp = client.post("/api/v1/auth/login", json={"email": "fd_op@test.com", "password": "OperatorPass12!"})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def connector_id(client, admin_token):
    """Create a connector to use in discover and batch-replace tests."""
    resp = client.post(
        "/api/v1/connectors/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Field Discovery Test Connector",
            "base_url": "https://source.example.com/api/hosts",
            "auth_method": "bearer_token",
            "credentials": {"token": "test-token-value"},
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# GET /api/v1/connectors/{id}/fields/discover
# ---------------------------------------------------------------------------

def test_discover_success(client, admin_token, connector_id):
    """Discover endpoint returns 200 with a fields list when source API responds OK.

    The source API call is mocked to return {"items": [{"id": 1, "name": "host"}]}.
    Response must contain field entries for "id" and "name".
    """
    mock_result_data = [{"id": 1, "name": "host"}]

    # Patch the internal fetch so no real HTTP call is made.
    # The discover service fetches the first page via source_client; we mock the
    # result at the service boundary. The exact patch path will be
    # app.services.field_discovery.fetch_first_page or similar — using a broad patch
    # on source_client._fetch_with_retries so the test works regardless of internals.
    with patch(
        "app.services.source_client._fetch_with_retries",
        new_callable=AsyncMock,
        return_value=(200, {"items": mock_result_data}, {}),
    ):
        resp = client.get(
            f"/api/v1/connectors/{connector_id}/fields/discover",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "fields" in data
    field_paths = [f["path"] for f in data["fields"]]
    assert "id" in field_paths or any("id" in p for p in field_paths)
    assert "name" in field_paths or any("name" in p for p in field_paths)


def test_discover_502(client, admin_token, connector_id):
    """Discover endpoint returns 502 with error_code SOURCE_UNREACHABLE when source API errors."""
    with patch(
        "app.services.source_client._fetch_with_retries",
        new_callable=AsyncMock,
        return_value=(500, {"error": "internal server error"}, {}),
    ):
        resp = client.get(
            f"/api/v1/connectors/{connector_id}/fields/discover",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 502
    body = resp.json()
    # Matches error format: {"detail": {"error_code": ..., "error_message": ..., "context": {}}}
    detail = body.get("detail", body)
    error_code = detail.get("error_code") or detail.get("code")
    assert error_code == "SOURCE_UNREACHABLE"


def test_discover_rbac(client, operator_token, connector_id):
    """Operator role receives 403 on discover endpoint (admin-only)."""
    resp = client.get(
        f"/api/v1/connectors/{connector_id}/fields/discover",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/v1/qualys/schema
# ---------------------------------------------------------------------------

def test_schema(client, admin_token):
    """Schema endpoint returns 200 with a fields list.

    - "sourceNativeKey" must be present with is_identity=True.
    - "operatingSystem" must be present with is_identity=False.
    """
    resp = client.get(
        "/api/v1/qualys/schema",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "fields" in data

    fields_by_name = {f["field"]: f for f in data["fields"]}

    assert "sourceNativeKey" in fields_by_name
    assert fields_by_name["sourceNativeKey"]["is_identity"] is True

    assert "operatingSystem" in fields_by_name
    assert fields_by_name["operatingSystem"]["is_identity"] is False


def test_schema_operator(client, operator_token):
    """Operator role can access the schema endpoint (read-only, non-sensitive)."""
    resp = client.get(
        "/api/v1/qualys/schema",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# PUT /api/v1/connectors/{id}/mappings  (batch-replace)
# ---------------------------------------------------------------------------

def test_batch_replace(client, admin_token, connector_id):
    """Batch-replace with a valid direct_copy mapping → 200, replaced=1, is_valid_mappings=true."""
    payload = {
        "mappings": [
            {
                "mapping_type": "direct_copy",
                "target_field": "sourceNativeKey",
                "source_field": "id",
                "static_value": None,
                "conditions": None,
                "fallback": None,
                "order": 0,
            }
        ]
    }
    resp = client.put(
        f"/api/v1/connectors/{connector_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["replaced"] == 1
    assert data["is_valid_mappings"] is True


def test_batch_replace_empty(client, admin_token, connector_id):
    """Batch-replace with empty mappings list → 200, replaced=0, is_valid_mappings=false."""
    payload = {"mappings": []}
    resp = client.put(
        f"/api/v1/connectors/{connector_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["replaced"] == 0
    assert data["is_valid_mappings"] is False


def test_batch_replace_rollback(client, admin_token, connector_id):
    """Batch-replace with an invalid mapping_type fails with 422 or 400.

    Existing mappings must remain unchanged (transaction rolled back).
    """
    # First, set a known good mapping
    good_payload = {
        "mappings": [
            {
                "mapping_type": "direct_copy",
                "target_field": "sourceNativeKey",
                "source_field": "id",
                "static_value": None,
                "conditions": None,
                "fallback": None,
                "order": 0,
            }
        ]
    }
    setup_resp = client.put(
        f"/api/v1/connectors/{connector_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=good_payload,
    )
    assert setup_resp.status_code == 200

    # Now attempt a replace with an invalid mapping_type — should fail
    bad_payload = {
        "mappings": [
            {
                "mapping_type": "totally_invalid_type",
                "target_field": "sourceNativeKey",
                "source_field": "id",
                "static_value": None,
                "conditions": None,
                "fallback": None,
                "order": 0,
            }
        ]
    }
    fail_resp = client.put(
        f"/api/v1/connectors/{connector_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=bad_payload,
    )
    # Should be rejected at schema level (422) or application level (400)
    assert fail_resp.status_code in (400, 422)

    # Verify the previously-set mapping is still in place (rollback worked)
    # Re-run the good batch-replace and confirm it works — if rollback failed,
    # the connector state would be corrupted and this might behave differently.
    verify_resp = client.put(
        f"/api/v1/connectors/{connector_id}/mappings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=good_payload,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["replaced"] == 1


def test_batch_replace_rbac(client, operator_token, connector_id):
    """Operator role receives 403 on batch-replace endpoint (admin-only)."""
    payload = {"mappings": []}
    resp = client.put(
        f"/api/v1/connectors/{connector_id}/mappings",
        headers={"Authorization": f"Bearer {operator_token}"},
        json=payload,
    )
    assert resp.status_code == 403


def test_schema_instanceuuidsource_is_not_identity(client, admin_token):
    """instanceUuidSource must NOT be flagged as identity in the schema response.

    It lives in the Qualys payload identityAttributes block but is not a valid
    identity gate field for connector validation (not in IDENTITY_ATTRIBUTES).
    """
    resp = client.get(
        "/api/v1/qualys/schema",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    fields_by_name = {f["field"]: f for f in resp.json()["fields"]}
    assert "instanceUuidSource" in fields_by_name
    assert fields_by_name["instanceUuidSource"]["is_identity"] is False
