"""Verify QualysConfig ORM model matches Phase 34 schema."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.models.qualys_config import QualysConfig


def test_qualys_config_has_expected_columns():
    """QualysConfig should have exactly the Phase 34 column set."""
    columns = {c.name for c in QualysConfig.__table__.columns}
    expected = {"id", "username", "connector_uuid", "encrypted_password", "created_at", "updated_at"}
    assert columns == expected, f"Column mismatch: have {columns}, expected {expected}"


def test_qualys_config_connector_uuid_not_nullable():
    """connector_uuid must be NOT NULL after Phase 34 migration."""
    col = QualysConfig.__table__.columns["connector_uuid"]
    assert col.nullable is False, "connector_uuid must be NOT NULL"


def test_qualys_config_no_api_url_column():
    """api_url column must not exist after Phase 34."""
    columns = {c.name for c in QualysConfig.__table__.columns}
    assert "api_url" not in columns


def test_qualys_config_no_encrypted_token_column():
    """encrypted_token column must not exist after Phase 34."""
    columns = {c.name for c in QualysConfig.__table__.columns}
    assert "encrypted_token" not in columns
