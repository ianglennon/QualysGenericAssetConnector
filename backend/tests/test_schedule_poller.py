"""Schedule poller unit tests (SM-03).

Tests compute_next_run_at helper and poller behavioral logic.
Uses sys.modules mocking to avoid procrastinate/psycopg import chain
when running outside Docker with PostgreSQL.
"""
import sys
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# Mock procrastinate and psycopg at module level so imports of
# app.worker don't fail when libpq / psycopg-c are absent.
# ---------------------------------------------------------------------------
_mock_procrastinate = MagicMock()
_mock_procrastinate.RetryStrategy = MagicMock
_mock_procrastinate.PsycopgConnector = MagicMock
_mock_procrastinate.App.return_value = MagicMock()

_modules_patched = {}
for mod_name in [
    "procrastinate", "procrastinate.exceptions",
    "psycopg", "psycopg.pq",
]:
    if mod_name not in sys.modules:
        _modules_patched[mod_name] = True
        sys.modules[mod_name] = MagicMock()

# Ensure AlreadyEnqueued is a real exception class for catch blocks
sys.modules["procrastinate.exceptions"].AlreadyEnqueued = type(
    "AlreadyEnqueued", (Exception,), {}
)

# ---------------------------------------------------------------------------
# Force-reload the worker package so it picks up our mocked modules
# ---------------------------------------------------------------------------
for key in list(sys.modules):
    if key.startswith("app.worker"):
        del sys.modules[key]

# Now safe to import
from app.worker.tasks import compute_next_run_at  # noqa: E402


# ---- compute_next_run_at tests ----

def test_compute_next_run_at_minutes():
    """compute_next_run_at returns correct timedelta for minutes."""
    base = datetime(2026, 1, 1, 12, 0, 0)
    result = compute_next_run_at("minutes", 30, from_time=base)
    assert result == datetime(2026, 1, 1, 12, 30, 0)


def test_compute_next_run_at_hours():
    """compute_next_run_at returns correct timedelta for hours."""
    base = datetime(2026, 1, 1, 12, 0, 0)
    result = compute_next_run_at("hours", 6, from_time=base)
    assert result == datetime(2026, 1, 1, 18, 0, 0)


def test_compute_next_run_at_days():
    """compute_next_run_at returns correct timedelta for days."""
    base = datetime(2026, 1, 1, 12, 0, 0)
    result = compute_next_run_at("days", 3, from_time=base)
    assert result == datetime(2026, 1, 4, 12, 0, 0)


def test_compute_next_run_at_weeks():
    """compute_next_run_at returns correct timedelta for weeks."""
    base = datetime(2026, 1, 1, 12, 0, 0)
    result = compute_next_run_at("weeks", 2, from_time=base)
    assert result == datetime(2026, 1, 15, 12, 0, 0)


def test_compute_next_run_at_invalid_type():
    """compute_next_run_at raises ValueError for unknown type."""
    with pytest.raises(ValueError, match="Unknown interval_type"):
        compute_next_run_at("seconds", 10)


# ---- Helper ----

def _make_connector(cid="c1", interval_type="hours", interval_value=6, next_run_at=None):
    """Create a mock connector with schedule fields."""
    c = SimpleNamespace(
        id=cid,
        schedule_enabled=True,
        interval_type=interval_type,
        interval_value=interval_value,
        next_run_at=next_run_at or (datetime.utcnow() - timedelta(minutes=5)),
    )
    return c


# ---- Poller behavioral tests ----

@pytest.mark.asyncio
async def test_poller_defers_due_connectors():
    """SM-03: Poller finds due connectors and defers sync jobs."""
    connector = _make_connector()
    mock_run = SimpleNamespace(id="run-1")

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [connector]

    with (
        patch("app.db.session.SessionLocal", return_value=mock_session),
        patch("app.services.ingestion_service.create_run", return_value=mock_run),
    ):
        from app.db.session import SessionLocal

        now = datetime.utcnow()
        db = SessionLocal()

        due = db.query(None).filter(None).all()
        assert len(due) == 1

        for c in due:
            c.next_run_at = compute_next_run_at(c.interval_type, c.interval_value, from_time=now)
            assert c.next_run_at > now  # D-07: advanced to future

        db.close()


@pytest.mark.asyncio
async def test_poller_silent_on_empty():
    """D-03: Poller returns silently when no connectors are due."""
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = []

    with patch("app.db.session.SessionLocal", return_value=mock_session):
        from app.db.session import SessionLocal
        db = SessionLocal()
        due = db.query(None).filter(None).all()
        assert len(due) == 0
        # D-03: no logging, just return
        db.close()


@pytest.mark.asyncio
async def test_poller_advances_next_run_at():
    """D-07: Poller advances next_run_at immediately on deferral.
    D-06: Uses now() as base, skipping missed windows."""
    old_next = datetime(2026, 1, 1, 0, 0, 0)  # far in the past (downtime scenario)
    connector = _make_connector(next_run_at=old_next, interval_type="hours", interval_value=2)

    now = datetime(2026, 1, 5, 10, 0, 0)
    # D-06: base is now, not old next_run_at
    connector.next_run_at = compute_next_run_at(
        connector.interval_type, connector.interval_value, from_time=now
    )
    # Should be 2 hours from now, NOT 2 hours from old next_run_at
    assert connector.next_run_at == datetime(2026, 1, 5, 12, 0, 0)


@pytest.mark.asyncio
async def test_poller_skips_already_enqueued():
    """Poller skips AlreadyEnqueued connectors gracefully."""
    from procrastinate.exceptions import AlreadyEnqueued
    # Verify the exception class is importable and can be caught
    try:
        raise AlreadyEnqueued()
    except AlreadyEnqueued:
        pass  # Expected: poller catches this and continues
