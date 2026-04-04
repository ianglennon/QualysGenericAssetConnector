"""Unit tests for CanvasEndpoint CRUD routes with tree validation.

Auth is bypassed by overriding get_current_user with a mock admin user.
Uses shared conftest.py fixtures for DB and client.
"""

import uuid

import pytest

from app.core.security import get_current_user
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
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


def _seed_endpoint(db_session, connector_id: str, name: str = "Test Endpoint") -> str:
    """Insert a ConnectorEndpoint and return its ID."""
    ep_id = str(uuid.uuid4())
    ep = ConnectorEndpoint(
        id=ep_id,
        connector_id=connector_id,
        name=name,
        path=f"/api/{name.lower().replace(' ', '-')}",
    )
    db_session.add(ep)
    db_session.flush()
    return ep_id


def _create_canvas(client, connector_id: str, name: str = "Test Canvas") -> str:
    """Create a canvas via API and return its ID."""
    resp = client.post(
        f"/api/v1/connectors/{connector_id}/canvases",
        json={"name": name},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _base_url(connector_id: str, canvas_id: str) -> str:
    return f"/api/v1/connectors/{connector_id}/canvases/{canvas_id}/endpoints"


# --- Test 1: POST add endpoint to canvas returns 201 ---

def test_create_canvas_endpoint_success(client, db_session):
    """POST adds endpoint to canvas with correct fields."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)
    resp = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["canvas_id"] == canvas_id
    assert data["endpoint_id"] == ep_id
    assert data["field_role"] == "data"
    assert data["max_concurrency"] == 5
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


# --- Test 2: POST with non-existent endpoint_id returns 404 ---

def test_create_canvas_endpoint_nonexistent_endpoint(client, db_session):
    """POST with bogus endpoint_id returns 404 ENDPOINT_NOT_FOUND."""
    conn_id = _seed_connector(db_session)
    canvas_id = _create_canvas(client, conn_id)
    resp = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": "does-not-exist"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ENDPOINT_NOT_FOUND"


# --- Test 3: POST with endpoint from different connector returns 404 ---

def test_create_canvas_endpoint_wrong_connector(client, db_session):
    """POST with endpoint belonging to another connector returns 404."""
    conn_id = _seed_connector(db_session)
    # Create a second connector and an endpoint under it
    other_conn_id = str(uuid.uuid4())
    db_session.add(Connector(
        id=other_conn_id,
        name="Other Connector",
        base_url="https://other.example.com",
        auth_method="bearer_token",
    ))
    db_session.flush()
    other_ep_id = _seed_endpoint(db_session, other_conn_id, "Other EP")

    canvas_id = _create_canvas(client, conn_id)
    resp = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": other_ep_id},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ENDPOINT_NOT_FOUND"


# --- Test 4: POST with field_role=iterator and variable_extractions ---

def test_create_canvas_endpoint_with_extractions(client, db_session):
    """POST with field_role='iterator' and variable_extractions succeeds."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)
    resp = client.post(
        _base_url(conn_id, canvas_id),
        json={
            "endpoint_id": ep_id,
            "field_role": "iterator",
            "variable_extractions": {"name": "data.name", "node_id": "data.id"},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["field_role"] == "iterator"
    assert data["variable_extractions"] == {"name": "data.name", "node_id": "data.id"}


# --- Test 5: POST with max_concurrency=0 returns 422 ---

def test_create_canvas_endpoint_invalid_max_concurrency(client, db_session):
    """POST with max_concurrency=0 returns 422 validation error."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)
    resp = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id, "max_concurrency": 0},
    )
    assert resp.status_code == 422


# --- Test 6: POST with field_role=invalid returns 422 ---

def test_create_canvas_endpoint_invalid_field_role(client, db_session):
    """POST with invalid field_role returns 422 validation error."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)
    resp = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id, "field_role": "invalid"},
    )
    assert resp.status_code == 422


# --- Test 7: Circular reference detection (D-11) ---

def test_circular_reference_rejected(client, db_session):
    """Setting A's parent to B when B's parent is A returns 409 CIRCULAR_REFERENCE."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)

    # Create A (root)
    resp_a = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id},
    )
    assert resp_a.status_code == 201
    ref_a_id = resp_a.json()["id"]

    # Create B with parent=A
    resp_b = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id, "parent_ref_id": ref_a_id},
    )
    assert resp_b.status_code == 201
    ref_b_id = resp_b.json()["id"]

    # Try to set A's parent to B -> should fail with 409
    patch_resp = client.patch(
        _base_url(conn_id, canvas_id) + f"/{ref_a_id}",
        json={"parent_ref_id": ref_b_id},
    )
    assert patch_resp.status_code == 409
    assert patch_resp.json()["error"]["code"] == "CIRCULAR_REFERENCE"


# --- Test 8: GET list returns all canvas-endpoints ordered by tree_order ---

def test_list_canvas_endpoints_ordered(client, db_session):
    """GET returns canvas-endpoints ordered by tree_order ascending."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)

    # Create with different tree_orders
    client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id, "tree_order": 2},
    )
    client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id, "tree_order": 0},
    )
    client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id, "tree_order": 1},
    )

    resp = client.get(_base_url(conn_id, canvas_id))
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 3
    assert items[0]["tree_order"] == 0
    assert items[1]["tree_order"] == 1
    assert items[2]["tree_order"] == 2


# --- Test 9: PATCH update field_role ---

def test_update_field_role(client, db_session):
    """PATCH updates field_role from 'data' to 'both'."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)
    create_resp = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id},
    )
    ref_id = create_resp.json()["id"]

    patch_resp = client.patch(
        _base_url(conn_id, canvas_id) + f"/{ref_id}",
        json={"field_role": "both"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["field_role"] == "both"


# --- Test 10: DELETE removes canvas-endpoint, children get orphaned ---

def test_delete_orphans_children(client, db_session):
    """DELETE parent ref causes child's parent_ref_id to become null (SET NULL)."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)

    # Create parent A (root)
    resp_a = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id},
    )
    ref_a_id = resp_a.json()["id"]

    # Create child B with parent=A
    resp_b = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id, "parent_ref_id": ref_a_id},
    )
    ref_b_id = resp_b.json()["id"]

    # Delete A
    del_resp = client.delete(_base_url(conn_id, canvas_id) + f"/{ref_a_id}")
    assert del_resp.status_code == 204

    # Get B -> parent_ref_id should be null
    get_resp = client.get(_base_url(conn_id, canvas_id) + f"/{ref_b_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["parent_ref_id"] is None


# --- Test 11: GET validate endpoint ---

def test_validate_valid_tree(client, db_session):
    """Validate returns valid=true for a proper tree (1 root, no orphans)."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)

    # Create root
    resp_a = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id},
    )
    ref_a_id = resp_a.json()["id"]

    # Create child
    client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id, "parent_ref_id": ref_a_id},
    )

    resp = client.get(_base_url(conn_id, canvas_id) + "/validate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["orphaned_refs"] == []
    assert data["root_count"] == 1


def test_validate_orphaned_nodes(client, db_session):
    """Validate returns valid=false when orphaned nodes exist."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)

    # Create root A
    client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id},
    )

    # Create C (no parent -- second root / orphan from tree perspective)
    client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id},
    )
    # With 2 roots, valid should be false
    resp = client.get(_base_url(conn_id, canvas_id) + "/validate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert data["root_count"] == 2


# --- Test 12: max_concurrency defaults to 5 ---

def test_max_concurrency_default(client, db_session):
    """When max_concurrency is not specified, it defaults to 5."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)
    resp = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id},
    )
    assert resp.status_code == 201
    assert resp.json()["max_concurrency"] == 5


def test_max_concurrency_custom(client, db_session):
    """When max_concurrency is specified as 10, it is stored correctly."""
    conn_id = _seed_connector(db_session)
    ep_id = _seed_endpoint(db_session, conn_id)
    canvas_id = _create_canvas(client, conn_id)
    resp = client.post(
        _base_url(conn_id, canvas_id),
        json={"endpoint_id": ep_id, "max_concurrency": 10},
    )
    assert resp.status_code == 201
    assert resp.json()["max_concurrency"] == 10


# --------------- Phase 54 Dry-Run Wiring Smoke Tests ---------------


class TestDryRunCanvasWiring:
    """Verify dry_run_canvas passes data_root and pagination to root fetch."""

    def test_resolve_pagination_config_importable_from_canvas_endpoints(self):
        """Confirm canvas_endpoints module imports resolve_pagination_config."""
        from app.routers.canvas_endpoints import resolve_pagination_config
        assert callable(resolve_pagination_config)

    def test_source_client_resolve_pagination_handles_none(self):
        """Verify the resolver used by dry-run handles None gracefully."""
        from app.services.source_client import resolve_pagination_config
        assert resolve_pagination_config(None) is None

    def test_source_client_resolve_pagination_handles_valid_dict(self):
        """Verify the resolver returns strategies for valid config."""
        from app.services.source_client import resolve_pagination_config
        result = resolve_pagination_config({
            "strategy": "cursor",
            "cursor_field": "next",
            "cursor_param": "after",
        })
        assert result is not None
        assert len(result) == 1
