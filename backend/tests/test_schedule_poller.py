"""Schedule poller unit tests (SM-03)."""
import pytest


def test_compute_next_run_at_minutes():
    """compute_next_run_at returns correct timedelta for minutes."""
    pytest.skip("Stub -- compute_next_run_at moves to app.worker.tasks in Plan 03")


def test_compute_next_run_at_hours():
    """compute_next_run_at returns correct timedelta for hours."""
    pytest.skip("Stub -- compute_next_run_at moves to app.worker.tasks in Plan 03")


def test_compute_next_run_at_days():
    """compute_next_run_at returns correct timedelta for days."""
    pytest.skip("Stub -- compute_next_run_at moves to app.worker.tasks in Plan 03")


def test_compute_next_run_at_weeks():
    """compute_next_run_at returns correct timedelta for weeks."""
    pytest.skip("Stub -- compute_next_run_at moves to app.worker.tasks in Plan 03")


@pytest.mark.asyncio
async def test_poller_defers_due_connectors():
    """SM-03: Poller finds due connectors and defers sync jobs."""
    pytest.skip("Stub -- implemented in Plan 03")


@pytest.mark.asyncio
async def test_poller_silent_on_empty():
    """D-03: Poller returns silently when no connectors are due."""
    pytest.skip("Stub -- implemented in Plan 03")


@pytest.mark.asyncio
async def test_poller_advances_next_run_at():
    """D-07: Poller advances next_run_at immediately on deferral."""
    pytest.skip("Stub -- implemented in Plan 03")
