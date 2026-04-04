"""Tests for Procrastinate task deferral and queueing_lock (TQ-03)."""
import pytest


@pytest.mark.xfail(reason="Wave 0 stub — implementation in Task 1")
def test_run_connector_sync_task_is_registered():
    """run_connector_sync task is importable and registered with procrastinate."""
    from app.worker.tasks import run_connector_sync
    assert hasattr(run_connector_sync, 'configure')


@pytest.mark.xfail(reason="Wave 0 stub — implementation in Plan 02")
def test_duplicate_defer_raises_already_enqueued():
    """Deferring same connector twice raises AlreadyEnqueued."""
    # Requires running Procrastinate infrastructure — tested in integration
    assert False, "Needs Procrastinate integration test setup"
