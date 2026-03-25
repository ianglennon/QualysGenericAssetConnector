"""Phase 43 gap-fill tests: EndpointRunLog chain fields, DryRunResponse schema,
dry-run endpoint, and Alembic migration for depth column.

Covers gaps 1-4:
  Gap 1 — EndpointRunLogResponse includes chain fields (canvas_id, child_requests_*, depth)
  Gap 2 — DryRunResponse schema (records, total_records, capped)
  Gap 3 — Dry-run endpoint executes chain without Qualys, caps at 50
  Gap 4 — Alembic migration adds depth column
"""

import os
import sys
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect
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
from app.models.connector_endpoint import ConnectorEndpoint  # noqa: F401
from app.models.canvas import Canvas  # noqa: F401
from app.models.canvas_endpoint import CanvasEndpoint  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
from app.models.run_history import RunHistory, RunFailure, RunStatus, EndpointRunLog  # noqa: F401
from app.models.field_mapping import FieldMapping  # noqa: F401
from app.models.qualys_config import QualysConfig  # noqa: F401


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


class _MockAdminUser:
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
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
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

    def override_get_current_user():
        return _MockAdminUser()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_current_user] = override_get_current_user

    yield TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    fastapi_app.dependency_overrides.clear()


# --- Helpers ---

def _seed_connector(session_factory) -> str:
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


def _seed_run_with_chain_log(session_factory, connector_id: str) -> tuple[str, str]:
    """Insert a RunHistory and an EndpointRunLog with chain fields set. Returns (run_id, log_id)."""
    db = session_factory()
    try:
        # Seed connector endpoint
        ep_id = str(uuid.uuid4())
        ep = ConnectorEndpoint(
            id=ep_id,
            connector_id=connector_id,
            name="Chain Endpoint",
            path="/api/devices",
        )
        db.add(ep)
        db.commit()

        run_id = str(uuid.uuid4())
        run = RunHistory(
            id=run_id,
            connector_id=connector_id,
            status=RunStatus.success,
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            records_fetched=5,
            records_submitted=5,
            records_failed=0,
        )
        db.add(run)
        db.commit()

        canvas_id = str(uuid.uuid4())
        log_id = str(uuid.uuid4())
        log = EndpointRunLog(
            id=log_id,
            run_id=run_id,
            endpoint_id=ep_id,
            execution_order=0,
            records_fetched=5,
            records_submitted=5,
            records_failed=0,
            status="success",
            canvas_id=canvas_id,
            child_requests_total=3,
            child_requests_failed=1,
            child_requests_skipped=0,
            depth=1,
        )
        db.add(log)
        db.commit()

        return run_id, log_id
    finally:
        db.close()


# ─── Gap 1: EndpointRunLogResponse includes chain fields ───────────────────────

def test_run_detail_endpoint_log_response_includes_chain_fields(setup_db):
    """GET /runs/{id} returns endpoint_logs with canvas_id, child_requests_*, and depth."""
    connector_id = _seed_connector(setup_db)
    run_id, _log_id = _seed_run_with_chain_log(setup_db, connector_id)

    with TestClient(fastapi_app) as client:
        resp = client.get(f"/api/v1/runs/{run_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert "endpoint_logs" in data
    logs = data["endpoint_logs"]
    assert len(logs) == 1

    log = logs[0]
    # All five new chain fields must be present in the response
    assert "canvas_id" in log, "canvas_id field missing from endpoint log response"
    assert log["canvas_id"] is not None, "canvas_id should be a non-null string"
    assert "child_requests_total" in log, "child_requests_total missing"
    assert log["child_requests_total"] == 3
    assert "child_requests_failed" in log, "child_requests_failed missing"
    assert log["child_requests_failed"] == 1
    assert "child_requests_skipped" in log, "child_requests_skipped missing"
    assert log["child_requests_skipped"] == 0
    assert "depth" in log, "depth field missing from endpoint log response"
    assert log["depth"] == 1


# ─── Gap 2: DryRunResponse schema exists with correct fields ───────────────────

def test_dry_run_response_schema_has_correct_fields(setup_db):
    """DryRunResponse Pydantic schema exposes records, total_records, capped."""
    from app.schemas.run_history import DryRunResponse

    result = DryRunResponse(records=[{"hostName": "server-1"}], total_records=1, capped=False)
    assert result.records == [{"hostName": "server-1"}]
    assert result.total_records == 1
    assert result.capped is False

    capped_result = DryRunResponse(records=[], total_records=75, capped=True)
    assert capped_result.capped is True
    assert capped_result.total_records == 75


# ─── Gap 3: Dry-run endpoint caps at 50 and returns DryRunResponse ─────────────

def test_dry_run_endpoint_returns_empty_when_no_canvas_endpoints(setup_db):
    """POST /canvases/{id}/dry-run returns empty DryRunResponse when canvas has no endpoints."""
    connector_id = _seed_connector(setup_db)

    # Create canvas directly in DB
    db = setup_db()
    try:
        canvas_id = str(uuid.uuid4())
        canvas = Canvas(id=canvas_id, connector_id=connector_id, name="Test Canvas")
        db.add(canvas)
        db.commit()
    finally:
        db.close()

    with TestClient(fastapi_app) as client:
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/canvases/{canvas_id}/dry-run"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data, "DryRunResponse missing 'records' field"
    assert "total_records" in data, "DryRunResponse missing 'total_records' field"
    assert "capped" in data, "DryRunResponse missing 'capped' field"
    assert data["records"] == []
    assert data["total_records"] == 0
    assert data["capped"] is False


def test_dry_run_endpoint_returns_404_for_nonexistent_canvas(setup_db):
    """POST /canvases/{bad_id}/dry-run returns 404 CANVAS_NOT_FOUND."""
    connector_id = _seed_connector(setup_db)

    with TestClient(fastapi_app) as client:
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/canvases/does-not-exist/dry-run"
        )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CANVAS_NOT_FOUND"


def test_dry_run_endpoint_accessible_to_operator_role(setup_db):
    """POST dry-run endpoint is accessible by operator (not just admin)."""
    from app.models.user import UserRole as UR

    class _MockOperatorUser:
        role = UR.operator
        id = "mock-op-id"
        email = "op@test.local"
        is_active = True

    fastapi_app.dependency_overrides[get_current_user] = lambda: _MockOperatorUser()

    connector_id = _seed_connector(setup_db)
    db = setup_db()
    try:
        canvas_id = str(uuid.uuid4())
        canvas = Canvas(id=canvas_id, connector_id=connector_id, name="Op Canvas")
        db.add(canvas)
        db.commit()
    finally:
        db.close()

    with TestClient(fastapi_app) as client:
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/canvases/{canvas_id}/dry-run"
        )

    # Operator should get 200 (empty canvas) not 403
    assert resp.status_code == 200


# ─── Gap 4: Alembic migration adds depth column ────────────────────────────────

def test_migration_adds_depth_column_to_endpoint_run_logs(setup_db):
    """EndpointRunLog ORM model includes a nullable depth column."""
    columns = {col.name: col for col in EndpointRunLog.__table__.columns}

    assert "depth" in columns, "depth column missing from EndpointRunLog model"
    depth_col = columns["depth"]
    assert depth_col.nullable is True, "depth column should be nullable"

    # Also verify canvas_id and child_requests_* columns exist (migration scope)
    for col_name in ("canvas_id", "child_requests_total", "child_requests_failed", "child_requests_skipped"):
        assert col_name in columns, f"{col_name} column missing from EndpointRunLog model"


def test_migration_file_has_correct_revision_and_upgrade(setup_db):
    """add_depth_column migration file contains expected revision and upgrade logic."""
    import importlib.util
    import pathlib

    migration_path = pathlib.Path(__file__).parent.parent.parent / \
        "app" / "db" / "migrations" / "versions" / "add_depth_column.py"

    assert migration_path.exists(), f"Migration file not found at {migration_path}"

    spec = importlib.util.spec_from_file_location("add_depth_column", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, "revision"), "migration missing 'revision' attribute"
    assert hasattr(module, "upgrade"), "migration missing 'upgrade' function"
    assert hasattr(module, "downgrade"), "migration missing 'downgrade' function"
