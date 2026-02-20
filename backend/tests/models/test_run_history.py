import os
import sys
import sqlalchemy as sa

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.models.run_history import RunHistory, RunFailure


def test_run_history_columns():
    columns = {column.name: column for column in RunHistory.__table__.columns}
    expected = {
        "id",
        "connector_id",
        "status",
        "started_at",
        "finished_at",
        "records_fetched",
        "records_submitted",
        "records_failed",
        "error_type",
        "error_message",
        "error_context",
        "created_at",
    }
    assert expected.issubset(columns.keys())
    assert isinstance(columns["error_context"].type, sa.JSON)


def test_run_failure_columns():
    columns = {column.name: column for column in RunFailure.__table__.columns}
    expected = {
        "id",
        "run_id",
        "record_identifier",
        "error_message",
        "created_at",
    }
    assert expected.issubset(columns.keys())
