"""Tests for Procrastinate worker lifecycle (TQ-01)."""
import pytest


@pytest.mark.xfail(reason="Wave 0 stub — implementation in Task 2")
def test_lifespan_starts_procrastinate_worker():
    """Worker task is created during FastAPI lifespan startup."""
    from app.main import _worker_task
    # After lifespan startup, _worker_task should be an asyncio.Task
    assert _worker_task is not None


def test_health_endpoint_reports_worker_status(client):
    """GET /health returns worker field."""
    response = client.get("/health")
    assert "worker" in response.json()
