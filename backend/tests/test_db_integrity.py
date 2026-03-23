"""Tests for DB integrity verification (DBRS-01, DBRS-02).

Covers verify_db_integrity() behavior:
- All tables present: logs info and returns normally
- Missing tables: stamps Alembic to base and re-runs upgrade
- Still missing after re-migration: sys.exit(1)
- Missing tables: emits ERROR log listing missing names
- EXPECTED_TABLES constant matches all 8 model __tablename__ values
"""

import pytest
from unittest.mock import patch, MagicMock

from app.main import EXPECTED_TABLES, verify_db_integrity


ALL_TABLES = list(EXPECTED_TABLES)
SEVEN_TABLES = [t for t in ALL_TABLES if t != "users"]


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
