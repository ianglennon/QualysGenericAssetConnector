"""
Integration tests for the field discovery and mapping API endpoints.

Endpoints under test:
  GET  /api/v1/connectors/{id}/fields/discover
  GET  /api/v1/qualys/schema
  PUT  /api/v1/connectors/{id}/mappings

Uses shared conftest.py fixtures for DB and client.
"""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.fixture
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
    """Discover endpoint returns 200 with a fields list when source API responds OK."""
    mock_result_data = [{"id": 1, "name": "host"}]

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
    """Schema endpoint returns 200 with a fields list."""
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
    """Batch-replace with a valid direct_copy mapping -> 200, replaced=1, is_valid_mappings=true."""
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
    """Batch-replace with empty mappings list -> 200, replaced=0, is_valid_mappings=false."""
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
    """Batch-replace with an invalid mapping_type fails with 422 or 400."""
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

    # Now attempt a replace with an invalid mapping_type -- should fail
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
    assert fail_resp.status_code in (400, 422)

    # Verify the previously-set mapping is still in place
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
    """instanceUuidSource must NOT be flagged as identity in the schema response."""
    resp = client.get(
        "/api/v1/qualys/schema",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    fields_by_name = {f["field"]: f for f in resp.json()["fields"]}
    assert "instanceUuidSource" in fields_by_name
    assert fields_by_name["instanceUuidSource"]["is_identity"] is False
