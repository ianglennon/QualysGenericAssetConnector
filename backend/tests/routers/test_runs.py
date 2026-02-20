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


@pytest.fixture(scope="module")
def admin_token(client):
    db = SessionLocal()
    create_user(db, "runs_admin@test.com", "AdminPass12!", UserRole.admin)
    db.close()
    resp = client.post("/api/v1/auth/login", json={"email": "runs_admin@test.com", "password": "AdminPass12!"})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def operator_token(client):
    db = SessionLocal()
    create_user(db, "runs_op@test.com", "OperatorPass12!", UserRole.operator)
    db.close()
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
    assert len(data) >= 3
    run_ids = {run["id"] for run in data}
    assert seeded_runs["run1_id"] in run_ids
    assert seeded_runs["run2_id"] in run_ids

    run2 = next(run for run in data if run["id"] == seeded_runs["run2_id"])
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
    assert len(data) == 2
    for run in data:
        assert run["connector_id"] == connector_id


def test_list_connector_runs_not_found(client, admin_token):
    resp = client.get(
        "/api/v1/connectors/nonexistent-connector-id/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CONNECTOR_NOT_FOUND"


def _create_connector(name="Runs Trigger Connector"):
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
        return connector.id
    finally:
        db.close()


def test_trigger_run_as_admin_returns_202(client, admin_token):
    connector_id = _create_connector(name="Runs Trigger Admin")
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
    connector_id = _create_connector(name="Runs Trigger Operator")
    with patch("app.routers.runs.run_ingestion", new_callable=AsyncMock) as mock_run:
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/runs",
            headers={"Authorization": f"Bearer {operator_token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    mock_run.assert_awaited_once_with(data["run_id"])


def test_trigger_run_conflict_when_running_exists(client, admin_token):
    connector_id = _create_connector(name="Runs Trigger Conflict")
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
    connector_id = _create_connector(name="Runs Trigger Status")

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
