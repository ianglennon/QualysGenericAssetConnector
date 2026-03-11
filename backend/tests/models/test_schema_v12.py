import os
import sys
import sqlalchemy as sa

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.models.connector_endpoint import ConnectorEndpoint
from app.models.run_history import EndpointRunLog
from app.models.field_mapping import FieldMapping
from app.models.connector import Connector


def test_connector_endpoint_columns():
    columns = {column.name: column for column in ConnectorEndpoint.__table__.columns}
    expected = {
        "id",
        "connector_id",
        "name",
        "path",
        "pagination_config",
        "is_enabled",
        "display_order",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(columns.keys())
    assert isinstance(columns["pagination_config"].type, sa.JSON)
    assert isinstance(columns["is_enabled"].type, sa.Integer)


def test_endpoint_run_log_columns():
    columns = {column.name: column for column in EndpointRunLog.__table__.columns}
    expected = {
        "id",
        "run_id",
        "endpoint_id",
        "execution_order",
        "records_fetched",
        "records_submitted",
        "records_failed",
        "status",
        "error_message",
        "created_at",
    }
    assert expected.issubset(columns.keys())
    # status must be String (not Enum) — consistent with project convention for new models
    assert isinstance(columns["status"].type, sa.String)


def test_field_mapping_columns():
    columns = {column.name: column for column in FieldMapping.__table__.columns}
    assert "endpoint_id" in columns
    assert "connector_id" not in columns


def test_connector_columns():
    columns = {column.name: column for column in Connector.__table__.columns}
    assert "test_path" in columns
    assert "pagination_config" not in columns
