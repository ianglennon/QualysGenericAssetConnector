"""Integration tests for delete cascade behavior on canvases and endpoints.

Validates:
- Canvas deletion cascades to canvas_endpoints, field_mappings, and unshared connector_endpoints
- Endpoint deletion blocked (409) when assigned to a canvas
- Endpoint deletion succeeds when not assigned to any canvas
"""

import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.main import app as fastapi_app
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.base import Base
from app.models import connector_endpoint as _ce_mod  # noqa: F401
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.field_mapping import FieldMapping
from app.models.run_history import RunHistory, RunFailure, EndpointRunLog  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
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

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_current_user] = lambda: _MockAdminUser()

    yield TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_connector(sf) -> str:
    cid = str(uuid.uuid4())
    db = sf()
    db.add(Connector(id=cid, name="Test", base_url="https://example.com", auth_method="bearer_token"))
    db.commit()
    db.close()
    return cid


def _seed_endpoint(sf, connector_id: str, name: str = "ep") -> str:
    eid = str(uuid.uuid4())
    db = sf()
    db.add(ConnectorEndpoint(id=eid, connector_id=connector_id, name=name, path="/test"))
    db.commit()
    db.close()
    return eid


def _seed_canvas(sf, connector_id: str, name: str = "canvas") -> str:
    cid = str(uuid.uuid4())
    db = sf()
    db.add(Canvas(id=cid, connector_id=connector_id, name=name))
    db.commit()
    db.close()
    return cid


def _seed_canvas_endpoint(sf, canvas_id: str, endpoint_id: str) -> str:
    ceid = str(uuid.uuid4())
    db = sf()
    db.add(CanvasEndpoint(id=ceid, canvas_id=canvas_id, endpoint_id=endpoint_id))
    db.commit()
    db.close()
    return ceid


def _seed_field_mapping(sf, endpoint_id: str, canvas_id: str) -> str:
    fid = str(uuid.uuid4())
    db = sf()
    db.add(FieldMapping(
        id=fid,
        endpoint_id=endpoint_id,
        canvas_id=canvas_id,
        source_field="src",
        target_field="dst",
        mapping_type="direct_copy",
    ))
    db.commit()
    db.close()
    return fid


def _seed_run(sf, connector_id: str) -> str:
    from datetime import datetime
    rid = str(uuid.uuid4())
    db = sf()
    db.add(RunHistory(
        id=rid,
        connector_id=connector_id,
        status="success",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()
    return rid


def _seed_endpoint_run_log(sf, endpoint_id: str, run_id: str) -> str:
    lid = str(uuid.uuid4())
    db = sf()
    db.add(EndpointRunLog(
        id=lid,
        run_id=run_id,
        endpoint_id=endpoint_id,
        execution_order=0,
        status="success",
    ))
    db.commit()
    db.close()
    return lid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_canvas_delete_cascades_dependent_records(setup_db):
    """Deleting a canvas removes canvas_endpoints, field_mappings,
    and unshared connector_endpoints (with their run logs)."""
    sf = setup_db
    cid = _seed_connector(sf)
    eid = _seed_endpoint(sf, cid, "ep1")
    canvas_id = _seed_canvas(sf, cid, "Canvas A")
    _seed_canvas_endpoint(sf, canvas_id, eid)
    _seed_field_mapping(sf, eid, canvas_id)

    run_id = _seed_run(sf, cid)
    _seed_endpoint_run_log(sf, eid, run_id)

    with TestClient(fastapi_app) as client:
        resp = client.delete(f"/api/v1/connectors/{cid}/canvases/{canvas_id}")

    assert resp.status_code == 204

    # Verify cascade cleanup
    db = sf()
    assert db.query(CanvasEndpoint).filter_by(canvas_id=canvas_id).count() == 0
    assert db.query(FieldMapping).filter_by(canvas_id=canvas_id).count() == 0
    # Unshared endpoint should be deleted
    assert db.query(ConnectorEndpoint).filter_by(id=eid).count() == 0
    # Endpoint run logs cleaned up with endpoint
    assert db.query(EndpointRunLog).filter_by(endpoint_id=eid).count() == 0
    db.close()


def test_canvas_delete_preserves_shared_endpoint(setup_db):
    """When an endpoint is assigned to two canvases, deleting one canvas
    preserves the endpoint and its assignment to the other canvas."""
    sf = setup_db
    cid = _seed_connector(sf)
    eid = _seed_endpoint(sf, cid, "shared-ep")
    canvas_a = _seed_canvas(sf, cid, "Canvas A")
    canvas_b = _seed_canvas(sf, cid, "Canvas B")
    _seed_canvas_endpoint(sf, canvas_a, eid)
    _seed_canvas_endpoint(sf, canvas_b, eid)

    with TestClient(fastapi_app) as client:
        resp = client.delete(f"/api/v1/connectors/{cid}/canvases/{canvas_a}")

    assert resp.status_code == 204

    db = sf()
    # Shared endpoint still exists
    assert db.query(ConnectorEndpoint).filter_by(id=eid).count() == 1
    # Canvas B assignment still exists
    assert db.query(CanvasEndpoint).filter_by(canvas_id=canvas_b, endpoint_id=eid).count() == 1
    db.close()


def test_endpoint_delete_blocked_when_assigned_to_canvas(setup_db):
    """DELETE endpoint returns 409 ENDPOINT_IN_USE when the endpoint
    is assigned to at least one canvas, with canvas names in response."""
    sf = setup_db
    cid = _seed_connector(sf)
    eid = _seed_endpoint(sf, cid, "guarded-ep")
    canvas_id = _seed_canvas(sf, cid, "My Canvas")
    _seed_canvas_endpoint(sf, canvas_id, eid)

    with TestClient(fastapi_app) as client:
        resp = client.delete(f"/api/v1/connectors/{cid}/endpoints/{eid}")

    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "ENDPOINT_IN_USE"
    assert "My Canvas" in body["error"]["details"]["canvas_names"]

    # Endpoint still exists
    db = sf()
    assert db.query(ConnectorEndpoint).filter_by(id=eid).count() == 1
    db.close()


def test_endpoint_delete_succeeds_when_unassigned(setup_db):
    """DELETE endpoint returns 204 when not assigned to any canvas,
    and cleans up run logs and field mappings."""
    sf = setup_db
    cid = _seed_connector(sf)
    eid = _seed_endpoint(sf, cid, "orphan-ep")

    run_id = _seed_run(sf, cid)
    _seed_endpoint_run_log(sf, eid, run_id)

    # Field mapping with no canvas (endpoint-only)
    fid = str(uuid.uuid4())
    db = sf()
    db.add(FieldMapping(
        id=fid,
        endpoint_id=eid,
        canvas_id=None,
        source_field="src",
        target_field="dst",
        mapping_type="direct_copy",
    ))
    db.commit()
    db.close()

    with TestClient(fastapi_app) as client:
        resp = client.delete(f"/api/v1/connectors/{cid}/endpoints/{eid}")

    assert resp.status_code == 204

    db = sf()
    assert db.query(ConnectorEndpoint).filter_by(id=eid).count() == 0
    assert db.query(EndpointRunLog).filter_by(endpoint_id=eid).count() == 0
    assert db.query(FieldMapping).filter_by(id=fid).count() == 0
    db.close()


def test_canvas_delete_returns_404_for_nonexistent(setup_db):
    """DELETE for a non-existent canvas returns 404 CANVAS_NOT_FOUND."""
    sf = setup_db
    cid = _seed_connector(sf)

    with TestClient(fastapi_app) as client:
        resp = client.delete(f"/api/v1/connectors/{cid}/canvases/nonexistent")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CANVAS_NOT_FOUND"
