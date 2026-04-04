"""Tests for Procrastinate worker lifecycle (TQ-01)."""
import asyncio
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch, call


def test_health_endpoint_reports_worker_status(client):
    """GET /health returns worker field."""
    response = client.get("/health")
    assert "worker" in response.json()


def test_procrastinate_lifecycle_opens_async_connection_and_starts_worker():
    """_procrastinate_lifecycle opens procrastinate_app.open_async() and starts worker task.

    TQ-01: Async worker must start inside FastAPI lifespan and shut down cleanly.
    This test exercises _procrastinate_lifecycle in isolation with mocked Procrastinate
    internals — no live PostgreSQL or libpq connection required.
    """
    import app.main as main_module
    from app.main import _procrastinate_lifecycle
    from app.core.settings import get_settings

    settings = get_settings()

    call_order = []

    # Mock the SQLAlchemy session used for CREATE SCHEMA
    mock_db = MagicMock()
    mock_db_class = MagicMock(return_value=mock_db)

    # Mock SyncPsycopgConnector and its app context
    mock_sync_app = MagicMock()
    mock_sync_app.__enter__ = MagicMock(return_value=mock_sync_app)
    mock_sync_app.__exit__ = MagicMock(return_value=False)
    mock_sync_app.open.return_value = mock_sync_app

    mock_procrastinate_app_cls = MagicMock(return_value=mock_sync_app)

    # open_async must be an async context manager
    @asynccontextmanager
    async def _mock_open_async():
        call_order.append("open_async")
        yield

    mock_proc_app = MagicMock()
    mock_proc_app.open_async = _mock_open_async

    # Track calls to run_worker_async by wrapping it.
    # We record args before any await so cancellation doesn't prevent tracking.
    run_worker_calls = []

    async def _never_ending_worker(**kwargs):
        # Record before any await point so cancellation doesn't skip this
        run_worker_calls.append(kwargs)
        await asyncio.sleep(9999)

    mock_proc_app.run_worker_async = _never_ending_worker

    async def run_lifecycle():
        async with _procrastinate_lifecycle(settings):
            # Yield a brief slot to the event loop so the created_task starts
            await asyncio.sleep(0)

    with (
        patch("app.main.SessionLocal", mock_db_class),
        patch("app.main.procrastinate.SyncPsycopgConnector"),
        patch("app.main.procrastinate.App", mock_procrastinate_app_cls),
        patch("app.main.procrastinate_app", mock_proc_app),
    ):
        asyncio.run(run_lifecycle())

    # Verify open_async was entered
    assert "open_async" in call_order, "procrastinate_app.open_async() was never called"

    # Verify worker was started with correct arguments
    assert len(run_worker_calls) == 1, (
        f"run_worker_async was expected to be called once, got {len(run_worker_calls)} calls"
    )
    assert run_worker_calls[0].get("install_signal_handlers") is False, (
        f"run_worker_async must be called with install_signal_handlers=False, "
        f"got kwargs: {run_worker_calls[0]}"
    )


def test_procrastinate_lifecycle_cancels_worker_on_shutdown():
    """_procrastinate_lifecycle cancels the worker task during lifespan shutdown.

    TQ-01 (D-02): Graceful shutdown — worker task must be cancelled and awaited.
    """
    import app.main as main_module
    from app.main import _procrastinate_lifecycle
    from app.core.settings import get_settings

    settings = get_settings()

    shutdown_events = []

    mock_db = MagicMock()
    mock_db_class = MagicMock(return_value=mock_db)

    mock_sync_app = MagicMock()
    mock_sync_app.__enter__ = MagicMock(return_value=mock_sync_app)
    mock_sync_app.__exit__ = MagicMock(return_value=False)
    mock_sync_app.open.return_value = mock_sync_app

    @asynccontextmanager
    async def _mock_open_async():
        yield

    mock_proc_app = MagicMock()
    mock_proc_app.open_async = _mock_open_async

    async def _cancellable_worker(**kwargs):
        try:
            # Brief yield so the task starts before cancel() is called
            await asyncio.sleep(0)
            await asyncio.sleep(9999)
        except asyncio.CancelledError:
            shutdown_events.append("worker_cancelled")
            raise

    mock_proc_app.run_worker_async = _cancellable_worker

    async def run_lifecycle():
        async with _procrastinate_lifecycle(settings):
            # Yield to event loop so the worker task actually starts
            await asyncio.sleep(0)

    with (
        patch("app.main.SessionLocal", mock_db_class),
        patch("app.main.procrastinate.SyncPsycopgConnector"),
        patch("app.main.procrastinate.App", return_value=mock_sync_app),
        patch("app.main.procrastinate_app", mock_proc_app),
    ):
        asyncio.run(run_lifecycle())

    assert "worker_cancelled" in shutdown_events, (
        "Worker task was not cancelled during lifespan shutdown"
    )

    # After lifecycle exits, _worker_task must be reset to None
    assert main_module._worker_task is None, "_worker_task must be None after shutdown"
