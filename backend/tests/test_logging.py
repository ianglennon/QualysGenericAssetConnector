"""
Tests for LOG-01: Verify that Alembic's fileConfig call does not silence
pre-existing uvicorn loggers after run_migrations() completes.

Root cause: Python's logging.config.fileConfig() defaults to
disable_existing_loggers=True, which disables all loggers registered before
the call. Alembic's env.py calls fileConfig(config.config_file_name) which
would silence uvicorn's loggers that were registered at startup.

Fix: Add `disable_existing_loggers = false` to the [loggers] section of
alembic.ini. fileConfig() reads this key and passes it as a keyword argument.
"""
import logging
import pytest
from app.main import run_migrations


class CapturingHandler(logging.Handler):
    """A logging handler that records all emitted records."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_run_migrations_preserves_uvicorn_access_logger():
    """uvicorn.access logger must not be disabled after run_migrations()."""
    uvicorn_access = logging.getLogger("uvicorn.access")
    # Ensure it is enabled before we call run_migrations
    uvicorn_access.disabled = False

    run_migrations()

    assert uvicorn_access.disabled is False, (
        "uvicorn.access logger was disabled by Alembic fileConfig. "
        "Add `disable_existing_loggers = false` to [loggers] in alembic.ini."
    )


def test_run_migrations_preserves_uvicorn_error_logger():
    """uvicorn.error logger must not be disabled after run_migrations()."""
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.disabled = False

    run_migrations()

    assert uvicorn_error.disabled is False, (
        "uvicorn.error logger was disabled by Alembic fileConfig. "
        "Add `disable_existing_loggers = false` to [loggers] in alembic.ini."
    )


def test_post_migration_error_log_visible():
    """A logging.error() call on a pre-existing logger must be captured after run_migrations().

    This proves the logger is active (not silently dropped).
    """
    sentinel_logger = logging.getLogger("test.sentinel.postmigration")
    sentinel_logger.setLevel(logging.DEBUG)
    sentinel_logger.disabled = False
    sentinel_logger.propagate = False

    handler = CapturingHandler()
    handler.setLevel(logging.DEBUG)
    sentinel_logger.addHandler(handler)

    try:
        run_migrations()
        sentinel_logger.error("post-migration error log test")

        assert len(handler.records) == 1, (
            f"Expected 1 log record after run_migrations(), got {len(handler.records)}. "
            "Logger may have been silenced by Alembic fileConfig. "
            "Add `disable_existing_loggers = false` to [loggers] in alembic.ini."
        )
        assert handler.records[0].getMessage() == "post-migration error log test"
    finally:
        sentinel_logger.removeHandler(handler)
