"""Integration tests for delete cascade behavior on canvases and endpoints.

Validates:
- Canvas deletion cascades to canvas_endpoints, field_mappings, and unshared connector_endpoints
- Endpoint deletion blocked (409) when assigned to a canvas
- Endpoint deletion succeeds when not assigned to any canvas

Auth is bypassed by overriding get_current_user with a mock admin user.
Uses shared conftest.py fixtures for DB and client.
"""

import uuid
from datetime import datetime

import pytest

from app.core.security import get_current_user
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.field_mapping import FieldMapping
from app.models.run_history import RunHistory, EndpointRunLog
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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_connector(db_session) -> str:
    cid = str(uuid.uuid4())
    db_session.add(Connector(id=cid, name="Test", base_url="https://example.com", auth_method="bearer_token"))
    db_session.flush()
    return cid


def _seed_endpoint(db_session, connector_id: str, name: str = "ep") -> str:
    eid = str(uuid.uuid4())
    db_session.add(ConnectorEndpoint(id=eid, connector_id=connector_id, name=name, path="/test"))
    db_session.flush()
    return eid


def _seed_canvas(db_session, connector_id: str, name: str = "canvas") -> str:
    cid = str(uuid.uuid4())
    db_session.add(Canvas(id=cid, connector_id=connector_id, name=name))
    db_session.flush()
    return cid


def _seed_canvas_endpoint(db_session, canvas_id: str, endpoint_id: str) -> str:
    ceid = str(uuid.uuid4())
    db_session.add(CanvasEndpoint(id=ceid, canvas_id=canvas_id, endpoint_id=endpoint_id))
    db_session.flush()
    return ceid


def _seed_field_mapping(db_session, endpoint_id: str, canvas_id: str) -> str:
    fid = str(uuid.uuid4())
    db_session.add(FieldMapping(
        id=fid,
        endpoint_id=endpoint_id,
        canvas_id=canvas_id,
        source_field="src",
        target_field="dst",
        mapping_type="direct_copy",
    ))
    db_session.flush()
    return fid


def _seed_run(db_session, connector_id: str) -> str:
    rid = str(uuid.uuid4())
    db_session.add(RunHistory(
        id=rid,
        connector_id=connector_id,
        status="success",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    ))
    db_session.flush()
    return rid


def _seed_endpoint_run_log(db_session, endpoint_id: str, run_id: str) -> str:
    lid = str(uuid.uuid4())
    db_session.add(EndpointRunLog(
        id=lid,
        run_id=run_id,
        endpoint_id=endpoint_id,
        execution_order=0,
        status="success",
    ))
    db_session.flush()
    return lid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_canvas_delete_cascades_dependent_records(client, db_session):
    """Deleting a canvas removes canvas_endpoints, field_mappings,
    and unshared connector_endpoints (with their run logs)."""
    cid = _seed_connector(db_session)
    eid = _seed_endpoint(db_session, cid, "ep1")
    canvas_id = _seed_canvas(db_session, cid, "Canvas A")
    _seed_canvas_endpoint(db_session, canvas_id, eid)
    _seed_field_mapping(db_session, eid, canvas_id)

    run_id = _seed_run(db_session, cid)
    _seed_endpoint_run_log(db_session, eid, run_id)

    resp = client.delete(f"/api/v1/connectors/{cid}/canvases/{canvas_id}")

    assert resp.status_code == 204

    # Verify cascade cleanup
    db_session.expire_all()
    assert db_session.query(CanvasEndpoint).filter_by(canvas_id=canvas_id).count() == 0
    assert db_session.query(FieldMapping).filter_by(canvas_id=canvas_id).count() == 0
    # Unshared endpoint should be deleted
    assert db_session.query(ConnectorEndpoint).filter_by(id=eid).count() == 0
    # Endpoint run logs cleaned up with endpoint
    assert db_session.query(EndpointRunLog).filter_by(endpoint_id=eid).count() == 0


def test_canvas_delete_preserves_shared_endpoint(client, db_session):
    """When an endpoint is assigned to two canvases, deleting one canvas
    preserves the endpoint and its assignment to the other canvas."""
    cid = _seed_connector(db_session)
    eid = _seed_endpoint(db_session, cid, "shared-ep")
    canvas_a = _seed_canvas(db_session, cid, "Canvas A")
    canvas_b = _seed_canvas(db_session, cid, "Canvas B")
    _seed_canvas_endpoint(db_session, canvas_a, eid)
    _seed_canvas_endpoint(db_session, canvas_b, eid)

    resp = client.delete(f"/api/v1/connectors/{cid}/canvases/{canvas_a}")

    assert resp.status_code == 204

    db_session.expire_all()
    # Shared endpoint still exists
    assert db_session.query(ConnectorEndpoint).filter_by(id=eid).count() == 1
    # Canvas B assignment still exists
    assert db_session.query(CanvasEndpoint).filter_by(canvas_id=canvas_b, endpoint_id=eid).count() == 1


def test_endpoint_delete_blocked_when_assigned_to_canvas(client, db_session):
    """DELETE endpoint returns 409 ENDPOINT_IN_USE when the endpoint
    is assigned to at least one canvas, with canvas names in response."""
    cid = _seed_connector(db_session)
    eid = _seed_endpoint(db_session, cid, "guarded-ep")
    canvas_id = _seed_canvas(db_session, cid, "My Canvas")
    _seed_canvas_endpoint(db_session, canvas_id, eid)

    resp = client.delete(f"/api/v1/connectors/{cid}/endpoints/{eid}")

    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "ENDPOINT_IN_USE"
    assert "My Canvas" in body["error"]["details"]["canvas_names"]

    # Endpoint still exists
    db_session.expire_all()
    assert db_session.query(ConnectorEndpoint).filter_by(id=eid).count() == 1


def test_endpoint_delete_succeeds_when_unassigned(client, db_session):
    """DELETE endpoint returns 204 when not assigned to any canvas,
    and cleans up run logs and field mappings."""
    cid = _seed_connector(db_session)
    eid = _seed_endpoint(db_session, cid, "orphan-ep")

    run_id = _seed_run(db_session, cid)
    _seed_endpoint_run_log(db_session, eid, run_id)

    # Field mapping with no canvas (endpoint-only)
    fid = str(uuid.uuid4())
    db_session.add(FieldMapping(
        id=fid,
        endpoint_id=eid,
        canvas_id=None,
        source_field="src",
        target_field="dst",
        mapping_type="direct_copy",
    ))
    db_session.flush()

    resp = client.delete(f"/api/v1/connectors/{cid}/endpoints/{eid}")

    assert resp.status_code == 204

    db_session.expire_all()
    assert db_session.query(ConnectorEndpoint).filter_by(id=eid).count() == 0
    assert db_session.query(EndpointRunLog).filter_by(endpoint_id=eid).count() == 0
    assert db_session.query(FieldMapping).filter_by(id=fid).count() == 0


def test_canvas_delete_returns_404_for_nonexistent(client, db_session):
    """DELETE for a non-existent canvas returns 404 CANVAS_NOT_FOUND."""
    cid = _seed_connector(db_session)

    resp = client.delete(f"/api/v1/connectors/{cid}/canvases/nonexistent")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CANVAS_NOT_FOUND"


def test_canvas_delete_preserves_endpoint_run_logs_with_stale_canvas_id(client, db_session):
    """DEL-07: EndpointRunLog records that carry a canvas_id string referencing
    a deleted canvas must survive because canvas_id is a plain String column
    with NO foreign key -- there is no CASCADE to fire on canvas deletion.

    Scenario: endpoint is shared by two canvases.  A run log is recorded with
    canvas_id = canvas_a.  When canvas_a is deleted the shared endpoint is
    preserved (shared with canvas_b) and the run log must also be preserved as
    an immutable historical audit record.
    """
    cid = _seed_connector(db_session)
    eid = _seed_endpoint(db_session, cid, "shared-ep-for-runlog")
    canvas_a = _seed_canvas(db_session, cid, "Canvas A")
    canvas_b = _seed_canvas(db_session, cid, "Canvas B")
    _seed_canvas_endpoint(db_session, canvas_a, eid)
    _seed_canvas_endpoint(db_session, canvas_b, eid)

    # Seed a run log that records activity for this endpoint under canvas_a
    run_id = _seed_run(db_session, cid)
    log_id = _seed_endpoint_run_log(db_session, eid, run_id)

    # Manually set the canvas_id on the run log to simulate a real run record
    log = db_session.query(EndpointRunLog).filter_by(id=log_id).first()
    log.canvas_id = canvas_a
    db_session.flush()

    # Delete canvas_a
    resp = client.delete(f"/api/v1/connectors/{cid}/canvases/{canvas_a}")

    assert resp.status_code == 204

    db_session.expire_all()
    # The shared endpoint still exists (assigned to canvas_b)
    assert db_session.query(ConnectorEndpoint).filter_by(id=eid).count() == 1

    # The run log must NOT be deleted -- canvas_id is a plain String with no FK
    surviving_log = db_session.query(EndpointRunLog).filter_by(id=log_id).first()
    assert surviving_log is not None, (
        "EndpointRunLog with canvas_id referencing deleted canvas must be preserved "
        "(canvas_id is a plain String column with no FK -- no CASCADE applies)"
    )
    # The canvas_id field still holds the now-stale reference (expected -- no cleanup)
    assert surviving_log.canvas_id == canvas_a
