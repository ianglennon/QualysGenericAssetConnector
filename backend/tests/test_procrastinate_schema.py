"""Tests for Procrastinate schema bootstrapping (TQ-04)."""
import asyncio
import pytest
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch, call


def test_procrastinate_schema_namespace_created_before_apply_schema():
    """_procrastinate_lifecycle executes CREATE SCHEMA IF NOT EXISTS before apply_schema().

    TQ-04 (D-09): The procrastinate schema namespace must exist before
    apply_schema() is called, otherwise apply_schema() will fail with a
    PostgreSQL 'schema does not exist' error.
    """
    from app.main import _procrastinate_lifecycle
    from app.core.settings import get_settings

    settings = get_settings()
    call_order = []

    # Mock SessionLocal to intercept schema creation SQL
    mock_db = MagicMock()
    mock_db.execute.side_effect = lambda stmt, *a, **kw: call_order.append("create_schema")
    mock_db.commit.return_value = None

    mock_session_local = MagicMock(return_value=mock_db)

    # Mock the sync app returned by procrastinate.App(connector=sync_connector)
    mock_sync_app = MagicMock()
    mock_sync_app.__enter__ = MagicMock(return_value=mock_sync_app)
    mock_sync_app.__exit__ = MagicMock(return_value=False)
    mock_sync_app.open.return_value = mock_sync_app
    mock_sync_app.schema_manager.apply_schema.side_effect = (
        lambda: call_order.append("apply_schema")
    )

    mock_procrastinate_app_cls = MagicMock(return_value=mock_sync_app)

    @asynccontextmanager
    async def _mock_open_async():
        yield

    mock_proc_app = MagicMock()
    mock_proc_app.open_async = _mock_open_async

    async def _noop_worker(**kwargs):
        await asyncio.sleep(9999)

    mock_proc_app.run_worker_async = _noop_worker

    async def run_lifecycle():
        async with _procrastinate_lifecycle(settings):
            pass

    with (
        patch("app.main.SessionLocal", mock_session_local),
        patch("app.main.procrastinate.SyncPsycopgConnector"),
        patch("app.main.procrastinate.App", mock_procrastinate_app_cls),
        patch("app.main.procrastinate_app", mock_proc_app),
    ):
        asyncio.run(run_lifecycle())

    # Both must have been called
    assert "create_schema" in call_order, (
        "CREATE SCHEMA IF NOT EXISTS was never called during _procrastinate_lifecycle"
    )
    assert "apply_schema" in call_order, (
        "apply_schema() was never called during _procrastinate_lifecycle"
    )

    # CREATE SCHEMA must come FIRST
    schema_idx = call_order.index("create_schema")
    apply_idx = call_order.index("apply_schema")
    assert schema_idx < apply_idx, (
        f"CREATE SCHEMA (pos {schema_idx}) must precede apply_schema (pos {apply_idx}); "
        f"call order: {call_order}"
    )


def test_procrastinate_schema_sql_contains_correct_statement():
    """_procrastinate_lifecycle issues CREATE SCHEMA IF NOT EXISTS procrastinate.

    TQ-04 (D-09): Verifies the exact SQL statement executed contains the
    'procrastinate' schema name and the IF NOT EXISTS guard (idempotent).
    """
    from app.main import _procrastinate_lifecycle
    from app.core.settings import get_settings

    settings = get_settings()
    executed_sql_texts = []

    mock_db = MagicMock()

    def _capture_sql(stmt, *a, **kw):
        # sa_text() objects have a .text attribute; MagicMock passes through __str__
        stmt_text = str(stmt)
        executed_sql_texts.append(stmt_text)

    mock_db.execute.side_effect = _capture_sql
    mock_session_local = MagicMock(return_value=mock_db)

    mock_sync_app = MagicMock()
    mock_sync_app.__enter__ = MagicMock(return_value=mock_sync_app)
    mock_sync_app.__exit__ = MagicMock(return_value=False)
    mock_sync_app.open.return_value = mock_sync_app

    @asynccontextmanager
    async def _mock_open_async():
        yield

    mock_proc_app = MagicMock()
    mock_proc_app.open_async = _mock_open_async

    async def _noop_worker(**kwargs):
        await asyncio.sleep(9999)

    mock_proc_app.run_worker_async = _noop_worker

    async def run_lifecycle():
        async with _procrastinate_lifecycle(settings):
            pass

    with (
        patch("app.main.SessionLocal", mock_session_local),
        patch("app.main.procrastinate.SyncPsycopgConnector"),
        patch("app.main.procrastinate.App", return_value=mock_sync_app),
        patch("app.main.procrastinate_app", mock_proc_app),
    ):
        asyncio.run(run_lifecycle())

    assert executed_sql_texts, "No SQL was executed via SessionLocal during _procrastinate_lifecycle"
    schema_sql = executed_sql_texts[0]
    assert "procrastinate" in schema_sql.lower(), (
        f"Expected schema name 'procrastinate' in SQL, got: {schema_sql!r}"
    )
    assert "if not exists" in schema_sql.lower(), (
        f"Expected IF NOT EXISTS guard in SQL (for idempotency), got: {schema_sql!r}"
    )
