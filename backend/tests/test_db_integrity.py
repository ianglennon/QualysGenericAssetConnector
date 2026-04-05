"""Tests for DB integrity verification (DBRS-01, DBRS-02) and Alembic migration baseline (DB-03).

Covers verify_db_integrity() behavior:
- All tables present: logs info and returns normally
- Missing tables: stamps Alembic to base and re-runs upgrade
- Still missing after re-migration: sys.exit(1)
- Missing tables: emits ERROR log listing missing names
- EXPECTED_TABLES constant matches all 8 model __tablename__ values

Covers DB-03 (Alembic baseline migration):
- Single Alembic head revision (001_baseline) exists
- Baseline migration creates all expected tables on a fresh PostgreSQL database
- Running upgrade head when already at head is idempotent (no error)
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy import inspect as sa_inspect
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory

from app.main import EXPECTED_TABLES, verify_db_integrity


ALL_TABLES = list(EXPECTED_TABLES)
SEVEN_TABLES = [t for t in ALL_TABLES if t != "users"]

# Test database URL — same PostgreSQL container, separate qualys_test database
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://qualys:qualys@db:5432/qualys_test"
)

# Path to alembic.ini inside the container (cwd is /app)
ALEMBIC_INI = "alembic.ini"


def _make_inspector(table_list):
    """Return a mock inspector whose get_table_names() returns table_list."""
    inspector = MagicMock()
    inspector.get_table_names.return_value = table_list
    return inspector


class TestExpectedTablesConstant:
    def test_expected_tables_constant_matches_models(self):
        expected = {
            "connectors",
            "connector_endpoints",
            "field_mappings",
            "qualys_config",
            "run_history",
            "run_failures",
            "endpoint_run_logs",
            "users",
            "canvases",
            "canvas_endpoints",
            "run_events",
            "roles",
            "role_permissions",
        }
        assert EXPECTED_TABLES == expected


class TestVerifyDbIntegrityAllPresent:
    @patch("app.main.sa_inspect")
    def test_verify_db_integrity_all_tables_present(self, mock_sa_inspect, caplog):
        """When all tables present, log info and return normally — no SystemExit."""
        mock_sa_inspect.return_value = _make_inspector(ALL_TABLES)

        import logging
        with caplog.at_level(logging.INFO, logger="app.main"):
            # Should not raise
            verify_db_integrity()

        assert any("DB integrity OK" in r.message for r in caplog.records)


class TestVerifyDbIntegrityMissingTables:
    @patch("app.main.command")
    @patch("app.main.sa_inspect")
    def test_verify_db_integrity_missing_tables_stamps_and_remigrates(
        self, mock_sa_inspect, mock_command
    ):
        """Missing tables: stamp to base then upgrade to head."""
        # First call returns 7 tables; second call (after re-migration) returns all 8
        mock_sa_inspect.side_effect = [
            _make_inspector(SEVEN_TABLES),
            _make_inspector(ALL_TABLES),
        ]

        verify_db_integrity()

        # stamp called with "base"
        assert mock_command.stamp.called
        call_args = mock_command.stamp.call_args
        assert call_args[0][1] == "base"

        # upgrade called with "head"
        assert mock_command.upgrade.called
        call_args = mock_command.upgrade.call_args
        assert call_args[0][1] == "head"

    @patch("app.main.command")
    @patch("app.main.sa_inspect")
    def test_verify_db_integrity_missing_tables_exits_if_still_missing(
        self, mock_sa_inspect, mock_command
    ):
        """If re-migration still leaves tables missing, sys.exit(1) is raised."""
        # Both calls return only 7 tables — re-migration did not help
        mock_sa_inspect.side_effect = [
            _make_inspector(SEVEN_TABLES),
            _make_inspector(SEVEN_TABLES),
        ]

        with pytest.raises(SystemExit) as exc_info:
            verify_db_integrity()

        assert exc_info.value.code == 1

    @patch("app.main.command")
    @patch("app.main.sa_inspect")
    def test_verify_db_integrity_logs_missing_tables(
        self, mock_sa_inspect, mock_command, caplog
    ):
        """Missing tables emit an ERROR log that names the missing table(s)."""
        mock_sa_inspect.side_effect = [
            _make_inspector(SEVEN_TABLES),
            _make_inspector(ALL_TABLES),
        ]

        import logging
        with caplog.at_level(logging.ERROR, logger="app.main"):
            verify_db_integrity()

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records, "Expected at least one ERROR log record"
        combined = " ".join(r.message for r in error_records)
        assert "missing tables" in combined.lower()
        assert "users" in combined


# ---------------------------------------------------------------------------
# DB-03: Alembic baseline migration tests
# ---------------------------------------------------------------------------

def _make_alembic_cfg(database_url: str) -> Config:
    """Build an Alembic Config pointed at the test database.

    Note: env.py overrides sqlalchemy.url via get_settings(), so callers must
    ensure DATABASE_URL env var is set to database_url before calling
    alembic.command.upgrade().
    """
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def _drop_all_tables(engine) -> None:
    """Drop all tables and Alembic version tracking from the test database.

    Uses CASCADE to handle FK dependencies.  Drops the alembic_version table
    so Alembic treats the schema as completely fresh.
    """
    with engine.connect() as conn:
        # Collect all non-system table names (includes alembic_version)
        inspector = sa_inspect(engine)
        tables = inspector.get_table_names()
        if tables:
            for t in tables:
                conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        # Also drop enum types created by the baseline migration
        conn.execute(text("DROP TYPE IF EXISTS userrole CASCADE"))
        conn.execute(text("DROP TYPE IF EXISTS runstatus CASCADE"))
        conn.commit()


def _run_alembic_upgrade_on_test_db(target: str = "head") -> None:
    """Run alembic upgrade against the test database.

    Temporarily overrides DATABASE_URL env var and clears the get_settings()
    LRU cache so env.py's get_settings() call picks up the test DB URL instead
    of the production URL.
    """
    import contextlib
    from app.core.settings import get_settings

    original_url = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = TEST_DATABASE_URL
        get_settings.cache_clear()
        cfg = _make_alembic_cfg(TEST_DATABASE_URL)
        command.upgrade(cfg, target)
    finally:
        if original_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_url
        get_settings.cache_clear()


class TestAlembicSingleHead:
    def test_alembic_has_exactly_one_head_revision(self):
        """DB-03(a): The Alembic script tree has exactly one head.

        This verifies no stray migration files remain that would
        create a multi-head situation causing 'alembic upgrade head' to fail.
        """
        cfg = Config(ALEMBIC_INI)
        script_dir = ScriptDirectory.from_config(cfg)
        heads = script_dir.get_heads()

        assert len(heads) == 1, (
            f"Expected exactly 1 Alembic head, found {len(heads)}: {heads}. "
            "Multiple heads mean 'alembic upgrade head' will fail."
        )


class TestAlembicBaselineMigrationCreatesAllTables:
    """DB-03(b): Running 'alembic upgrade head' from a blank schema creates all 11 tables.

    Uses a separate engine connection to the test database.  Drops all tables
    before the test to guarantee a clean-slate starting point, then runs the
    baseline migration and inspects the resulting table names.
    """

    @pytest.fixture(scope="class")
    def migrated_engine(self):
        """Drop all tables, run alembic upgrade head, yield engine, then restore."""
        from app.db.base import Base
        eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        _drop_all_tables(eng)

        _run_alembic_upgrade_on_test_db("head")

        yield eng

        # Restore: drop migration artifacts and rebuild from ORM metadata
        # so the conftest session-scoped engine still has working tables
        _drop_all_tables(eng)
        Base.metadata.create_all(bind=eng)
        eng.dispose()

    def test_baseline_migration_creates_all_expected_tables(self, migrated_engine):
        """All 11 tables from EXPECTED_TABLES are present after upgrade head."""
        inspector = sa_inspect(migrated_engine)
        actual_tables = set(inspector.get_table_names())

        missing = EXPECTED_TABLES - actual_tables
        assert not missing, (
            f"Baseline migration did not create these expected tables: {sorted(missing)}. "
            f"Tables actually present: {sorted(actual_tables)}"
        )

    def test_baseline_migration_creates_no_unexpected_tables(self, migrated_engine):
        """No tables beyond EXPECTED_TABLES + alembic_version are created."""
        inspector = sa_inspect(migrated_engine)
        actual_tables = set(inspector.get_table_names())
        # alembic_version is a legitimate extra table
        extra = actual_tables - EXPECTED_TABLES - {"alembic_version"}
        assert not extra, (
            f"Baseline migration created unexpected tables: {sorted(extra)}"
        )


class TestAlembicUpgradeHeadIsIdempotent:
    """DB-03(c): Running 'alembic upgrade head' when already at head does not error."""

    def test_upgrade_head_when_already_at_head_does_not_raise(self):
        """Running upgrade head twice in a row is safe — second call is a no-op."""
        from app.db.base import Base
        eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        _drop_all_tables(eng)

        try:
            # First run: apply migration from clean slate
            _run_alembic_upgrade_on_test_db("head")

            # Second run: already at head — must not raise
            _run_alembic_upgrade_on_test_db("head")
        finally:
            # Restore tables for subsequent tests
            _drop_all_tables(eng)
            Base.metadata.create_all(bind=eng)
            eng.dispose()
