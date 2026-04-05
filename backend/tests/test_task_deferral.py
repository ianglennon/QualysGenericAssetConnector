"""Tests for Procrastinate task deferral and queueing_lock (TQ-03)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping


def test_run_connector_sync_task_is_registered():
    """run_connector_sync task is importable and registered with procrastinate."""
    from app.worker.tasks import run_connector_sync
    assert hasattr(run_connector_sync, 'configure')


def _create_connector_with_endpoint(db_session, name="Deferral Test Connector"):
    """Create a connector with one enabled endpoint and identity mapping.

    Required so the trigger endpoint passes the CONN-02 guards before
    attempting deferral.
    """
    connector = Connector(
        name=name,
        base_url="https://deferral-test.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    db_session.flush()

    endpoint = ConnectorEndpoint(
        connector_id=connector.id,
        name="Default Endpoint",
        path="/api/hosts",
        is_enabled=True,
    )
    db_session.add(endpoint)
    db_session.flush()

    mapping = FieldMapping(
        endpoint_id=endpoint.id,
        target_field="hostName",
        mapping_type="direct_copy",
        source_field="name",
    )
    db_session.add(mapping)
    db_session.flush()

    return connector.id


def test_duplicate_defer_raises_already_enqueued_returns_409(client, admin_token, db_session):
    """Deferring the same connector sync twice returns HTTP 409.

    TQ-03: When AlreadyEnqueued is raised by Procrastinate's queueing_lock,
    the trigger endpoint must respond with 409 CONNECTOR_RUN_IN_PROGRESS
    and delete the orphaned RunHistory record.
    """
    # Use the SAME AlreadyEnqueued class that the router imported, to avoid
    # class identity issues if test_schedule_poller replaces the module attribute.
    import app.routers.runs as _runs_mod
    _AlreadyEnqueued = _runs_mod.AlreadyEnqueued

    connector_id = _create_connector_with_endpoint(db_session, name="Deferral Conflict Connector")

    # Build a mock configure chain that raises AlreadyEnqueued on defer_async
    mock_configured_task = MagicMock()
    mock_configured_task.defer_async = AsyncMock(side_effect=_AlreadyEnqueued())
    mock_configure = MagicMock(return_value=mock_configured_task)

    with patch("app.routers.runs.run_connector_sync") as mock_task:
        mock_task.configure = mock_configure

        resp = client.post(
            f"/api/v1/connectors/{connector_id}/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 409, (
        f"Expected 409 when AlreadyEnqueued is raised, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    # Error structure: {"error": {"code": "...", "message": "...", "context": {}}}
    error = body.get("error") or body.get("detail", {})
    if isinstance(error, dict):
        code = error.get("code") or error.get("error_code")
    else:
        code = None
    assert code == "CONNECTOR_RUN_IN_PROGRESS", (
        f"Expected error code CONNECTOR_RUN_IN_PROGRESS, got: {body}"
    )


def test_trigger_endpoint_defers_with_queueing_lock(client, admin_token, db_session):
    """Trigger endpoint calls run_connector_sync.configure with queueing_lock.

    TQ-03: The queueing_lock must be set to 'connector_{connector_id}' to
    prevent duplicate syncs for the same connector.
    """
    connector_id = _create_connector_with_endpoint(db_session, name="Deferral Lock Connector")

    mock_configured_task = MagicMock()
    mock_configured_task.defer_async = AsyncMock(return_value=None)
    mock_configure = MagicMock(return_value=mock_configured_task)

    with patch("app.routers.runs.run_connector_sync") as mock_task:
        mock_task.configure = mock_configure

        resp = client.post(
            f"/api/v1/connectors/{connector_id}/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 202, (
        f"Expected 202 from trigger endpoint, got {resp.status_code}: {resp.text}"
    )

    # Verify configure was called with queueing_lock for this connector
    mock_configure.assert_called_once()
    call_kwargs = mock_configure.call_args.kwargs
    assert call_kwargs.get("queueing_lock") == f"connector_{connector_id}", (
        f"Expected queueing_lock='connector_{connector_id}', got: {call_kwargs}"
    )

    # Verify defer_async was called with correct connector_id and run_id
    mock_configured_task.defer_async.assert_awaited_once()
    defer_kwargs = mock_configured_task.defer_async.call_args.kwargs
    assert defer_kwargs.get("connector_id") == str(connector_id)
    assert "run_id" in defer_kwargs
    assert defer_kwargs.get("triggered_by") == "manual"
