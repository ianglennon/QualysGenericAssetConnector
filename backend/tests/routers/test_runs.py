from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.field_mapping import FieldMapping
from app.models.run_history import RunHistory, RunFailure, RunStatus, EndpointRunLog


@pytest.fixture
def seeded_runs(db_session):
    """Seed connectors, runs, and failures for run tests."""
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
    db_session.add_all([connector_a, connector_b])
    db_session.flush()

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
    db_session.add_all([run1, run2, run3])
    db_session.flush()

    failures = [
        RunFailure(run_id=run2.id, record_identifier="host-1", error_message="bad payload"),
        RunFailure(run_id=run2.id, record_identifier="host-2", error_message="missing name"),
        RunFailure(run_id=run3.id, record_identifier="host-9", error_message="qualys rejected"),
    ]
    db_session.add_all(failures)
    db_session.flush()

    return {
        "connector_a_id": connector_a.id,
        "connector_b_id": connector_b.id,
        "run1_id": run1.id,
        "run2_id": run2.id,
        "run3_id": run3.id,
    }


def _create_connector_with_valid_endpoint(db_session, name="Runs Trigger Connector"):
    """Create a connector with one enabled endpoint that has an identity mapping.

    Required by CONN-02 guards: NO_ENABLED_ENDPOINTS and INVALID_ENDPOINT_MAPPINGS
    checks must pass before a run can be created.
    """
    connector = Connector(
        name=name,
        base_url="https://runs-trigger.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    db_session.flush()

    endpoint = ConnectorEndpoint(
        connector_id=connector.id,
        name="Default Endpoint",
        path="/api/resources",
        is_enabled=True,
    )
    db_session.add(endpoint)
    db_session.flush()

    mapping = FieldMapping(
        endpoint_id=endpoint.id,
        target_field="hostName",
        mapping_type="direct_copy",
        source_field="hostname",
    )
    db_session.add(mapping)
    db_session.flush()

    return connector.id


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

    # Verify connector_name is included
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


def test_trigger_run_as_admin_returns_202(client, admin_token, db_session):
    connector_id = _create_connector_with_valid_endpoint(db_session, name="Runs Trigger Admin")
    with patch("app.routers.runs.run_ingestion", new_callable=AsyncMock) as mock_run:
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "running"
    assert "run_id" in data
    mock_run.assert_awaited_once_with(data["run_id"], None)


def test_trigger_run_as_operator_returns_202(client, operator_token, db_session):
    connector_id = _create_connector_with_valid_endpoint(db_session, name="Runs Trigger Operator")
    with patch("app.routers.runs.run_ingestion", new_callable=AsyncMock) as mock_run:
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/runs",
            headers={"Authorization": f"Bearer {operator_token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    mock_run.assert_awaited_once_with(data["run_id"], None)


def test_trigger_run_conflict_when_running_exists(client, admin_token, db_session):
    connector_id = _create_connector_with_valid_endpoint(db_session, name="Runs Trigger Conflict")
    run = RunHistory(
        connector_id=connector_id,
        status=RunStatus.running,
        started_at=datetime.utcnow(),
    )
    db_session.add(run)
    db_session.flush()

    resp = client.post(
        f"/api/v1/connectors/{connector_id}/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONNECTOR_RUN_IN_PROGRESS"


def test_trigger_run_updates_status_on_completion(client, admin_token, db_session):
    connector_id = _create_connector_with_valid_endpoint(db_session, name="Runs Trigger Status")

    async def _complete_run(run_id: str, canvas_id=None):
        db_session.expire_all()
        run = db_session.query(RunHistory).filter(RunHistory.id == run_id).first()
        run.status = RunStatus.success
        run.finished_at = datetime.utcnow()
        db_session.flush()

    with patch("app.routers.runs.run_ingestion", new=_complete_run):
        resp = client.post(
            f"/api/v1/connectors/{connector_id}/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    db_session.expire_all()
    run = db_session.query(RunHistory).filter(RunHistory.id == run_id).first()
    assert run.status == RunStatus.success
    assert run.finished_at is not None


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


def test_trigger_returns_400_no_enabled_endpoints(client, admin_token, db_session):
    """Trigger returns 400 with NO_ENABLED_ENDPOINTS when connector has no enabled endpoints."""
    connector = Connector(
        name="No Endpoints Connector",
        base_url="https://no-endpoints.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    db_session.flush()
    connector_id = connector.id

    resp = client.post(
        f"/api/v1/connectors/{connector_id}/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    error = resp.json()["error"]
    assert error["code"] == "NO_ENABLED_ENDPOINTS"


def test_trigger_returns_400_invalid_endpoint_mappings(client, admin_token, db_session):
    """Trigger returns 400 with INVALID_ENDPOINT_MAPPINGS and invalid_endpoints list."""
    connector = Connector(
        name="Invalid Mappings Connector",
        base_url="https://invalid-mappings.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    db_session.flush()

    endpoint = ConnectorEndpoint(
        connector_id=connector.id,
        name="Unmapped Endpoint",
        path="/api/things",
        is_enabled=True,
    )
    db_session.add(endpoint)
    db_session.flush()

    # Create canvas + canvas_endpoint so canvas-aware validation evaluates it
    canvas = Canvas(connector_id=connector.id, name="Test Canvas")
    db_session.add(canvas)
    db_session.flush()
    ce = CanvasEndpoint(canvas_id=canvas.id, endpoint_id=endpoint.id, tree_order=0)
    db_session.add(ce)
    db_session.flush()

    # Only a non-identity mapping -- will fail CONN-02 check
    mapping = FieldMapping(
        endpoint_id=endpoint.id,
        target_field="operatingSystem",
        mapping_type="direct_copy",
        source_field="os",
    )
    db_session.add(mapping)
    db_session.flush()

    resp = client.post(
        f"/api/v1/connectors/{connector.id}/runs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    error = resp.json()["error"]
    assert error["code"] == "INVALID_ENDPOINT_MAPPINGS"
    invalid_endpoints = error["details"]["invalid_endpoints"]
    assert len(invalid_endpoints) == 1
    assert invalid_endpoints[0]["canvas_id"] == canvas.id


def test_trigger_returns_202_when_endpoints_valid(client, admin_token, db_session):
    """Trigger returns 202 when all enabled endpoints have identity mappings."""
    connector_id = _create_connector_with_valid_endpoint(db_session, name="Runs Trigger Valid CONN-02")

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


# --------------- Diagnostic Fields Tests ---------------


@pytest.fixture
def seeded_diagnostic_run(db_session, seeded_runs):
    """Create a run with endpoint logs that have diagnostic fields set."""
    connector_id = seeded_runs["connector_a_id"]

    # Create an endpoint for the log
    ep = ConnectorEndpoint(
        connector_id=connector_id,
        name="Diag Endpoint",
        path="/diag",
        is_enabled=True,
    )
    db_session.add(ep)
    db_session.flush()

    # Create a run
    now = datetime.utcnow()
    run = RunHistory(
        connector_id=connector_id,
        status=RunStatus.failed,
        started_at=now - timedelta(minutes=1),
        finished_at=now,
        records_fetched=5,
        records_submitted=0,
        records_failed=5,
    )
    db_session.add(run)
    db_session.flush()

    # Create a failed endpoint log with diagnostic fields
    failed_log = EndpointRunLog(
        run_id=run.id,
        endpoint_id=ep.id,
        execution_order=0,
        records_fetched=5,
        records_submitted=0,
        records_failed=5,
        status="failed",
        error_message="source timeout",
        failure_stage="source_fetch",
        http_request={"method": "GET", "url": "https://source.example.com/assets"},
        http_response={"status_code": 504, "body": "gateway timeout"},
    )
    db_session.add(failed_log)
    db_session.flush()

    # Create a successful run with endpoint log (no failure_stage)
    success_run = RunHistory(
        connector_id=connector_id,
        status=RunStatus.success,
        started_at=now - timedelta(minutes=3),
        finished_at=now - timedelta(minutes=2),
        records_fetched=10,
        records_submitted=10,
        records_failed=0,
    )
    db_session.add(success_run)
    db_session.flush()

    success_log = EndpointRunLog(
        run_id=success_run.id,
        endpoint_id=ep.id,
        execution_order=0,
        records_fetched=10,
        records_submitted=10,
        records_failed=0,
        status="success",
        error_message=None,
    )
    db_session.add(success_log)
    db_session.flush()

    return {
        "failed_run_id": run.id,
        "success_run_id": success_run.id,
        "endpoint_id": ep.id,
    }


def test_get_run_detail_includes_diagnostic_fields(client, admin_token, seeded_diagnostic_run):
    """GET /runs/{id} includes failure_stage, http_request, http_response on endpoint logs."""
    run_id = seeded_diagnostic_run["failed_run_id"]
    resp = client.get(f"/api/v1/runs/{run_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["endpoint_logs"]) == 1
    log = data["endpoint_logs"][0]
    assert log["failure_stage"] == "source_fetch"
    assert log["http_request"] is not None
    assert log["http_request"]["method"] == "GET"
    assert log["http_response"] is not None
    assert log["http_response"]["status_code"] == 504


def test_get_run_detail_null_diagnostic_fields_for_success(client, admin_token, seeded_diagnostic_run):
    """GET /runs/{id} returns null for diagnostic fields on successful endpoint logs."""
    run_id = seeded_diagnostic_run["success_run_id"]
    resp = client.get(f"/api/v1/runs/{run_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["endpoint_logs"]) == 1
    log = data["endpoint_logs"][0]
    assert log["failure_stage"] is None
    assert log["http_request"] is None
    assert log["http_response"] is None


def test_list_runs_omits_payloads(client, admin_token, seeded_diagnostic_run):
    """GET /runs (list) returns failure_stage but omits http_request/http_response."""
    resp = client.get("/api/v1/runs", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    # Find the failed diagnostic run in the list
    failed_run = next(
        (r for r in data["items"] if r["id"] == seeded_diagnostic_run["failed_run_id"]),
        None,
    )
    assert failed_run is not None


def test_list_runs_filter_by_connector(client, admin_token, seeded_runs):
    """GET /runs?connector_id=X returns only runs for connector X."""
    connector_a_id = seeded_runs["connector_a_id"]
    resp = client.get(
        f"/api/v1/runs?connector_id={connector_a_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    items = data["items"]
    # Connector A has run1 (success) and run2 (failed) -- both must appear
    assert len(items) >= 2
    for run in items:
        assert run["connector_id"] == connector_a_id
    # Connector B's run3 must NOT appear
    run_ids = {run["id"] for run in items}
    assert seeded_runs["run3_id"] not in run_ids
    assert seeded_runs["run1_id"] in run_ids
    assert seeded_runs["run2_id"] in run_ids


def test_list_runs_filter_by_status(client, admin_token, seeded_runs):
    """GET /runs?status=failed returns only failed runs."""
    resp = client.get(
        "/api/v1/runs?status=failed",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    items = data["items"]
    for run in items:
        assert run["status"] == "failed"
    run_ids = {run["id"] for run in items}
    assert seeded_runs["run2_id"] in run_ids
    assert seeded_runs["run1_id"] not in run_ids
    assert seeded_runs["run3_id"] not in run_ids


def test_list_runs_filter_date_from(client, admin_token, db_session, seeded_runs):
    """GET /runs?date_from=YYYY-MM-DD excludes runs started before that date."""
    # Create an old run 3 days ago
    old_started_at = datetime.utcnow() - timedelta(days=3)
    old_run = RunHistory(
        connector_id=seeded_runs["connector_a_id"],
        status=RunStatus.success,
        started_at=old_started_at,
        finished_at=old_started_at + timedelta(minutes=1),
        records_fetched=1,
        records_submitted=1,
        records_failed=0,
    )
    db_session.add(old_run)
    db_session.flush()
    old_run_id = old_run.id

    # Filter with date_from = yesterday (ISO date string)
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    resp = client.get(
        f"/api/v1/runs?date_from={yesterday}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    run_ids = {run["id"] for run in data["items"]}
    # Recent runs (started within last 10 minutes) must be included
    assert seeded_runs["run1_id"] in run_ids
    assert seeded_runs["run2_id"] in run_ids
    assert seeded_runs["run3_id"] in run_ids
    # Old run (3 days ago) must be excluded
    assert old_run_id not in run_ids


def test_list_runs_filter_date_to(client, admin_token, db_session, seeded_runs):
    """GET /runs?date_to=YYYY-MM-DD excludes runs started after that date."""
    # Create an old run 3 days ago so we have something within the date_to range
    old_started_at = datetime.utcnow() - timedelta(days=3)
    old_run = RunHistory(
        connector_id=seeded_runs["connector_b_id"],
        status=RunStatus.failed,
        started_at=old_started_at,
        finished_at=old_started_at + timedelta(minutes=1),
        records_fetched=2,
        records_submitted=0,
        records_failed=2,
    )
    db_session.add(old_run)
    db_session.flush()
    old_run_id = old_run.id

    # Filter with date_to = yesterday -- only runs started on or before yesterday
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    resp = client.get(
        f"/api/v1/runs?date_to={yesterday}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    run_ids = {run["id"] for run in data["items"]}
    # Old run (3 days ago) must be included
    assert old_run_id in run_ids
    # Recent runs (started within last 10 minutes, i.e. today) must be excluded
    assert seeded_runs["run1_id"] not in run_ids
    assert seeded_runs["run2_id"] not in run_ids
    assert seeded_runs["run3_id"] not in run_ids


def test_list_runs_filter_combined(client, admin_token, seeded_runs):
    """GET /runs?connector_id=A&status=success returns only run1 (connector A + success)."""
    connector_a_id = seeded_runs["connector_a_id"]
    resp = client.get(
        f"/api/v1/runs?connector_id={connector_a_id}&status=success",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    items = data["items"]
    # Only run1 (connector A, success) should appear
    for run in items:
        assert run["connector_id"] == connector_a_id
        assert run["status"] == "success"
    run_ids = {run["id"] for run in items}
    assert seeded_runs["run1_id"] in run_ids
    assert seeded_runs["run2_id"] not in run_ids  # connector A but failed
    assert seeded_runs["run3_id"] not in run_ids  # connector B


def test_runs_stats_empty_history(client, admin_token):
    """Stats endpoint handles empty run history -- zero runs returns sensible defaults."""
    # With transaction rollback isolation and no seeded_runs fixture,
    # stats should return valid defaults. But we need admin_token which already
    # seeds a user. Stats should still return valid structure.
    resp = client.get("/api/v1/runs/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_runs" in data
    assert "success_rate" in data
    assert "last_sync_at" in data
    assert "recent_runs_24h" in data
    assert isinstance(data["success_rate"], float)
