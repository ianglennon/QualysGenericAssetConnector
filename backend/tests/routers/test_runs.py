from datetime import datetime, timedelta
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_runs.db")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.main import create_app
from app.db.session import SessionLocal
from app.services.auth_service import create_user
from app.models.user import UserRole
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping
from app.models.run_history import RunHistory, RunFailure, RunStatus


@pytest.fixture(scope="module")
def client():
    db_path = os.path.abspath("test_runs.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    app = create_app()
    with TestClient(app) as c:
        yield c
    if os.path.exists(db_path):
        os.remove(db_path)


def _get_or_create_user(email: str, password: str, role: UserRole) -> None:
    """Create user if not already present (idempotent helper for module-scoped fixtures)."""
    from app.models.user import User
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if not existing:
            create_user(db, email, password, role)
    finally:
        db.close()


@pytest.fixture(scope="module")
def admin_token(client):
    _get_or_create_user("runs_admin@test.com", "AdminPass12!", UserRole.admin)
    resp = client.post("/api/v1/auth/login", json={"email": "runs_admin@test.com", "password": "AdminPass12!"})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def operator_token(client):
    _get_or_create_user("runs_op@test.com", "OperatorPass12!", UserRole.operator)
    resp = client.post("/api/v1/auth/login", json={"email": "runs_op@test.com", "password": "OperatorPass12!"})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def seeded_runs(client):
    db = SessionLocal()
    try:
        connector_a = Connector(
            name="Runs Connector A",
            base_url="https://runs-a.example.com",
            auth_method="bearer_token",
        )
        connector_b = Connector(
            name="Runs Connector B",
            base_url="https://runs-b.example.com",
            auth_method="api_key_header",
        )
        db.add_all([connector_a, connector_b])
        db.commit()
        db.refresh(connector_a)
        db.refresh(connector_b)

        now = datetime.utcnow()
        run1 = RunHistory(
            connector_id=connector_a.id,
            status=RunStatus.success,
            started_at=now - timedelta(minutes=10),
            finished_at=now - timedelta(minutes=5),
            records_fetched=10,
            records_submitted=10,
            records_failed=0,
        )
        run2 = RunHistory(
            connector_id=connector_a.id,
            status=RunStatus.failed,
            started_at=now - timedelta(minutes=4),
            finished_at=now - timedelta(minutes=3),
            records_fetched=5,
            records_submitted=0,
            records_failed=5,
            error_type="source_error",
            error_message="timeout",
            error_context={"page": 2},
        )
        run3 = RunHistory(
            connector_id=connector_b.id,
            status=RunStatus.partial_success,
            started_at=now - timedelta(minutes=2),
            finished_at=now - timedelta(minutes=1),
            records_fetched=8,
            records_submitted=6,
            records_failed=2,
        )
        db.add_all([run1, run2, run3])
        db.commit()
        db.refresh(run1)
        db.refresh(run2)
        db.refresh(run3)

        failures = [
            RunFailure(run_id=run2.id, record_identifier="host-1", error_message="bad payload"),
            RunFailure(run_id=run2.id, record_identifier="host-2", error_message="missing name"),
            RunFailure(run_id=run3.id, record_identifier="host-9", error_message="qualys rejected"),
        ]
        db.add_all(failures)
        db.commit()

        return {
            "connector_a_id": connector_a.id,
            "connector_b_id": connector_b.id,
            "run1_id": run1.id,
            "run2_id": run2.id,
            "run3_id": run3.id,
        }
    finally:
        db.close()


def test_list_runs_as_admin(client, admin_token, seeded_runs):
    resp = client.get("/api/v1/runs", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()

    # Verify paginated response structure
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 3

    run_ids = {run["id"] for run in data["items"]}
    assert seeded_runs["run1_id"] in run_ids
    assert seeded_runs["run2_id"] in run_ids

    # Verify connector_name is included (DB may contain runs from other tests, so just verify it's populated)
    for run in data["items"]:
        assert "connector_name" in run
        assert run["connector_name"] is not None

    run2 = next(run for run in data["items"] if run["id"] == seeded_runs["run2_id"])
    assert run2["status"] == "failed"
    assert run2["records_failed"] == 5
    assert run2["error_type"] == "source_error"
    assert run2["error_message"] == "timeout"
    assert run2["error_context"]["page"] == 2
    assert len(run2["failures"]) == 2


def test_list_runs_as_operator(client, operator_token, seeded_runs):
    resp = client.get("/api/v1/runs", headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 200


def test_get_run_by_id(client, operator_token, seeded_runs):
    run_id = seeded_runs["run2_id"]
    resp = client.get(f"/api/v1/runs/{run_id}", headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run_id
    assert data["status"] == "failed"
    assert data["error_type"] == "source_error"
    assert len(data["failures"]) == 2

    # Verify connector_name is included in detail view
    assert "connector_name" in data
    assert data["connector_name"] == "Runs Connector A"


def test_get_run_not_found(client, admin_token):
    resp = client.get("/api/v1/runs/nonexistent-run-id", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"


def test_list_connector_runs(client, admin_token, seeded_runs):
    connector_id = seeded_runs["connector_a_id"]
    resp = client.get(
        f"/api/v1/connectors/{connector_id}/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify paginated response structure
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 2

    for run in data["items"]:
        assert run["connector_id"] == connector_id
        # Verify connector_name is included
        assert "connector_name" in run
        assert run["connector_name"] == "Runs Connector A"


def test_list_connector_runs_not_found(client, admin_token):
    resp = client.get(
        "/api/v1/connectors/nonexistent-connector-id/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CONNECTOR_NOT_FOUND"


def _create_connector_with_valid_endpoint(name="Runs Trigger Connector"):
    """Create a connector with one enabled endpoint that has an identity mapping.

    Required by CONN-02 guards: NO_ENABLED_ENDPOINTS and INVALID_ENDPOINT_MAPPINGS
    checks must pass before a run can be created.
    """
    db = SessionLocal()
    try:
        connector = Connector(
            name=name,
            base_url="https://runs-trigger.example.com",
            auth_method="bearer_token",
        )
        db.add(connector)
        db.commit()
        db.refresh(connector)

        endpoint = ConnectorEndpoint(
            connector_id=connector.id,
            name="Default Endpoint",
            path="/api/resources",
            is_enabled=True,
        )
        db.add(endpoint)
        db.commit()
        db.refresh(endpoint)

        mapping = FieldMapping(
            endpoint_id=endpoint.id,
            target_field="hostName",
            mapping_type="direct_copy",
            source_field="hostname",
        )
        db.add(mapping)
        db.commit()

        return connector.id
    finally:
        db.close()


def test_trigger_run_as_admin_returns_202(client, admin_token):
    connector_id = _create_connector_with_valid_endpoint(name="Runs Trigger Admin")
    with patch("app.routers.runs.run_ingestion", new_callable=AsyncMock) as mock_run:
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "running"
    assert "run_id" in data
    mock_run.assert_awaited_once_with(data["run_id"])


def test_trigger_run_as_operator_returns_202(client, operator_token):
    connector_id = _create_connector_with_valid_endpoint(name="Runs Trigger Operator")
    with patch("app.routers.runs.run_ingestion", new_callable=AsyncMock) as mock_run:
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/runs",
            headers={"Authorization": f"Bearer {operator_token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    mock_run.assert_awaited_once_with(data["run_id"])


def test_trigger_run_conflict_when_running_exists(client, admin_token):
    connector_id = _create_connector_with_valid_endpoint(name="Runs Trigger Conflict")
    db = SessionLocal()
    try:
        run = RunHistory(
            connector_id=connector_id,
            status=RunStatus.running,
            started_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/connectors/{connector_id}/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONNECTOR_RUN_IN_PROGRESS"


def test_trigger_run_updates_status_on_completion(client, admin_token):
    connector_id = _create_connector_with_valid_endpoint(name="Runs Trigger Status")

    async def _complete_run(run_id: str):
        db = SessionLocal()
        try:
            run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
            run.status = RunStatus.success
            run.finished_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()

    with patch("app.routers.runs.run_ingestion", new=_complete_run):
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    db = SessionLocal()
    try:
        run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
        assert run.status == RunStatus.success
        assert run.finished_at is not None
    finally:
        db.close()


def test_pagination_initialized(client, admin_token, seeded_runs):
    """Smoke test: confirms add_pagination(app) is active and paginated response includes full metadata."""
    resp = client.get("/api/v1/runs", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data


def test_list_runs_pagination_params(client, admin_token, seeded_runs):
    """Test that pagination parameters work correctly."""
    resp = client.get(
        "/api/v1/runs?page=1&size=2",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 2


def test_partial_success_run_includes_failures(client, admin_token, seeded_runs):
    """Test that partial_success runs include failure samples."""
    run_id = seeded_runs["run3_id"]
    resp = client.get(
        f"/api/v1/runs/{run_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "partial_success"
    assert len(data["failures"]) >= 1
    assert data["failures"][0]["record_identifier"] == "host-9"


# New tests: CONN-02 trigger guards


def test_trigger_returns_400_no_enabled_endpoints(client, admin_token):
    """Trigger returns 400 with NO_ENABLED_ENDPOINTS when connector has no enabled endpoints."""
    db = SessionLocal()
    try:
        connector = Connector(
            name="No Endpoints Connector",
            base_url="https://no-endpoints.example.com",
            auth_method="bearer_token",
        )
        db.add(connector)
        db.commit()
        db.refresh(connector)
        connector_id = connector.id
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/connectors/{connector_id}/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    error = resp.json()["error"]
    assert error["code"] == "NO_ENABLED_ENDPOINTS"


def test_trigger_returns_400_invalid_endpoint_mappings(client, admin_token):
    """Trigger returns 400 with INVALID_ENDPOINT_MAPPINGS and invalid_endpoints list."""
    db = SessionLocal()
    try:
        connector = Connector(
            name="Invalid Mappings Connector",
            base_url="https://invalid-mappings.example.com",
            auth_method="bearer_token",
        )
        db.add(connector)
        db.commit()
        db.refresh(connector)

        endpoint = ConnectorEndpoint(
            connector_id=connector.id,
            name="Unmapped Endpoint",
            path="/api/things",
            is_enabled=True,
        )
        db.add(endpoint)
        db.commit()
        db.refresh(endpoint)

        # Only a non-identity mapping — will fail CONN-02 check
        mapping = FieldMapping(
            endpoint_id=endpoint.id,
            target_field="operatingSystem",
            mapping_type="direct_copy",
            source_field="os",
        )
        db.add(mapping)
        db.commit()

        connector_id = connector.id
        endpoint_id = endpoint.id
        endpoint_name = endpoint.name
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/connectors/{connector_id}/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    error = resp.json()["error"]
    assert error["code"] == "INVALID_ENDPOINT_MAPPINGS"
    invalid_endpoints = error["details"]["invalid_endpoints"]
    assert len(invalid_endpoints) == 1
    assert invalid_endpoints[0]["id"] == endpoint_id
    assert invalid_endpoints[0]["name"] == endpoint_name


def test_trigger_returns_202_when_endpoints_valid(client, admin_token):
    """Trigger returns 202 when all enabled endpoints have identity mappings."""
    connector_id = _create_connector_with_valid_endpoint(name="Runs Trigger Valid CONN-02")

    with patch("app.routers.runs.run_ingestion", new_callable=AsyncMock) as mock_run:
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "running"
    assert "run_id" in data


# Stats endpoint tests

def test_get_runs_stats(client, admin_token, seeded_runs):
    """GET /runs/stats returns 200 with all 4 required fields and sensible values."""
    resp = client.get("/api/v1/runs/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()

    # All 4 fields must be present
    assert "total_runs" in data
    assert "success_rate" in data
    assert "last_sync_at" in data
    assert "recent_runs_24h" in data

    # With seeded_runs (3 runs), totals should be >= 3
    assert data["total_runs"] >= 3

    # success_rate is a float 0.0 to 1.0
    assert isinstance(data["success_rate"], float)
    assert 0.0 <= data["success_rate"] <= 1.0

    # All seeded runs are within last 24h
    assert data["recent_runs_24h"] >= 3

    # last_sync_at is not None (at least one run has finished)
    assert data["last_sync_at"] is not None


def test_get_runs_stats_as_operator(client, operator_token, seeded_runs):
    """Stats endpoint is accessible by operator role."""
    resp = client.get("/api/v1/runs/stats", headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_runs" in data


def test_runs_stats_not_captured_as_run_id(client, admin_token, seeded_runs):
    """GET /runs/stats returns 200 (not 404 RUN_NOT_FOUND), confirming route order is correct."""
    resp = client.get("/api/v1/runs/stats", headers={"Authorization": f"Bearer {admin_token}"})
    # Must be 200, NOT 404 with RUN_NOT_FOUND
    assert resp.status_code == 200
    # Explicitly confirm it's not a RUN_NOT_FOUND error
    data = resp.json()
    assert "total_runs" in data
    assert "error" not in data


def test_runs_stats_empty_history():
    """Stats endpoint handles empty run history — zero runs edge case."""
    db_path = os.path.abspath("test_runs_empty_stats.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    # Spin up an isolated app with its own SQLite DB and session factory
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    from app.main import create_app as _create_app
    from app.db import session as _session_module

    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    IsolatedSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    empty_app = _create_app()

    def _override_get_db():
        db = IsolatedSession()
        try:
            db.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))
            yield db
        finally:
            db.close()

    from app.db.session import get_db
    empty_app.dependency_overrides[get_db] = _override_get_db

    try:
        with TestClient(empty_app) as empty_client:
            # Create admin user directly using isolated session
            _db = IsolatedSession()
            create_user(_db, "empty_stats_admin@test.com", "AdminPass12!", UserRole.admin)
            _db.close()

            # Log in
            login_resp = empty_client.post(
                "/api/v1/auth/login",
                json={"email": "empty_stats_admin@test.com", "password": "AdminPass12!"},
            )
            assert login_resp.status_code == 200, login_resp.text
            empty_token = login_resp.json()["access_token"]

            # Call stats on empty DB (no runs)
            resp = empty_client.get(
                "/api/v1/runs/stats",
                headers={"Authorization": f"Bearer {empty_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_runs"] == 0
            assert data["success_rate"] == 0.0
            assert data["last_sync_at"] is None
            assert data["recent_runs_24h"] == 0
    finally:
        engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)
