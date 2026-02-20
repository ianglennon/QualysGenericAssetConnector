"""Unit tests for validation service."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.models.connector import Connector
from app.models.field_mapping import FieldMapping
from app.services.validation import validate_connector_mappings, IDENTITY_ATTRIBUTES


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_validate_no_mappings_returns_false(db_session):
    """Test validation fails when no mappings exist."""
    # Create a connector with no mappings
    connector = Connector(
        id="test-connector-1",
        name="Test Connector",
        base_url="https://api.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    db_session.commit()
    
    is_valid, errors = validate_connector_mappings("test-connector-1", db_session)
    
    assert is_valid is False
    assert len(errors) == 1
    assert "Missing identity attribute" in errors[0]
    # Check that error message includes the full list
    for attr in IDENTITY_ATTRIBUTES:
        assert attr in errors[0]


def test_validate_with_identity_attribute_returns_true(db_session):
    """Test validation passes when identity attribute is mapped."""
    # Create connector and mapping with identity attribute
    connector = Connector(
        id="test-connector-2",
        name="Test Connector",
        base_url="https://api.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    
    mapping = FieldMapping(
        id="mapping-1",
        connector_id="test-connector-2",
        target_field="hostName",  # This is an identity attribute
        mapping_type="direct_copy",
        source_field="hostname",
    )
    db_session.add(mapping)
    db_session.commit()
    
    is_valid, errors = validate_connector_mappings("test-connector-2", db_session)
    
    assert is_valid is True
    assert len(errors) == 0


def test_validate_with_only_non_identity_fields_returns_false(db_session):
    """Test validation fails when only non-identity fields are mapped."""
    # Create connector and mappings with NO identity attributes
    connector = Connector(
        id="test-connector-3",
        name="Test Connector",
        base_url="https://api.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    
    # These are core attributes but NOT identity attributes
    mapping1 = FieldMapping(
        id="mapping-1",
        connector_id="test-connector-3",
        target_field="operatingSystem",
        mapping_type="direct_copy",
        source_field="os",
    )
    mapping2 = FieldMapping(
        id="mapping-2",
        connector_id="test-connector-3",
        target_field="lastLoggedOnUser",
        mapping_type="direct_copy",
        source_field="user",
    )
    db_session.add_all([mapping1, mapping2])
    db_session.commit()
    
    is_valid, errors = validate_connector_mappings("test-connector-3", db_session)
    
    assert is_valid is False
    assert len(errors) == 1
    assert "Missing identity attribute" in errors[0]


def test_validate_error_message_format(db_session):
    """Test that error message includes full attribute list in sorted order."""
    connector = Connector(
        id="test-connector-4",
        name="Test Connector",
        base_url="https://api.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    db_session.commit()
    
    is_valid, errors = validate_connector_mappings("test-connector-4", db_session)
    
    assert is_valid is False
    error_msg = errors[0]
    
    # Should start with standard prefix
    assert error_msg.startswith("Missing identity attribute. Valid identity attributes are:")
    
    # Should contain all identity attributes
    sorted_attrs = sorted(IDENTITY_ATTRIBUTES)
    for attr in sorted_attrs:
        assert attr in error_msg


def test_validate_multiple_identity_attributes_still_valid(db_session):
    """Test that having multiple identity attributes is valid."""
    connector = Connector(
        id="test-connector-5",
        name="Test Connector",
        base_url="https://api.example.com",
        auth_method="bearer_token",
    )
    db_session.add(connector)
    
    # Map multiple identity attributes
    mapping1 = FieldMapping(
        id="mapping-1",
        connector_id="test-connector-5",
        target_field="hostName",
        mapping_type="direct_copy",
        source_field="hostname",
    )
    mapping2 = FieldMapping(
        id="mapping-2",
        connector_id="test-connector-5",
        target_field="ipAddress",
        mapping_type="direct_copy",
        source_field="ip",
    )
    mapping3 = FieldMapping(
        id="mapping-3",
        connector_id="test-connector-5",
        target_field="macAddress",
        mapping_type="direct_copy",
        source_field="mac",
    )
    db_session.add_all([mapping1, mapping2, mapping3])
    db_session.commit()
    
    is_valid, errors = validate_connector_mappings("test-connector-5", db_session)
    
    assert is_valid is True
    assert len(errors) == 0
