"""Unit tests for validation service — validate_endpoint_mappings."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping
from app.services.validation import validate_endpoint_mappings, IDENTITY_ATTRIBUTES


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


def _make_connector(db, connector_id="connector-1"):
    connector = Connector(
        id=connector_id,
        name="Test Connector",
        base_url="https://api.example.com",
        auth_method="bearer_token",
    )
    db.add(connector)
    db.commit()
    return connector


def _make_endpoint(db, connector_id, endpoint_id, name="Endpoint 1", is_enabled=True):
    endpoint = ConnectorEndpoint(
        id=endpoint_id,
        connector_id=connector_id,
        name=name,
        path="/api/resources",
        is_enabled=is_enabled,
    )
    db.add(endpoint)
    db.commit()
    return endpoint


def _make_mapping(db, endpoint_id, mapping_id, target_field, source_field="field"):
    mapping = FieldMapping(
        id=mapping_id,
        endpoint_id=endpoint_id,
        target_field=target_field,
        mapping_type="direct_copy",
        source_field=source_field,
    )
    db.add(mapping)
    db.commit()
    return mapping


def test_no_enabled_endpoints_returns_valid(db_session):
    """Connector with no enabled endpoints returns (True, []) — guard is in run trigger."""
    _make_connector(db_session, "conn-no-endpoints")

    is_valid, invalid = validate_endpoint_mappings("conn-no-endpoints", db_session)

    assert is_valid is True
    assert invalid == []


def test_enabled_endpoint_with_identity_mapping_returns_valid(db_session):
    """Connector with enabled endpoint that has an identity mapping returns (True, [])."""
    _make_connector(db_session, "conn-valid")
    _make_endpoint(db_session, "conn-valid", "ep-valid", is_enabled=True)
    _make_mapping(db_session, "ep-valid", "map-1", target_field="hostName")

    is_valid, invalid = validate_endpoint_mappings("conn-valid", db_session)

    assert is_valid is True
    assert invalid == []


def test_enabled_endpoint_missing_identity_mapping_returns_invalid(db_session):
    """Connector with enabled endpoint that has no identity mapping returns (False, [{id, name}])."""
    _make_connector(db_session, "conn-invalid")
    endpoint = _make_endpoint(db_session, "conn-invalid", "ep-invalid", name="Bad Endpoint", is_enabled=True)
    # Map a non-identity field only
    _make_mapping(db_session, "ep-invalid", "map-bad", target_field="operatingSystem")

    is_valid, invalid = validate_endpoint_mappings("conn-invalid", db_session)

    assert is_valid is False
    assert len(invalid) == 1
    assert invalid[0]["id"] == endpoint.id
    assert invalid[0]["name"] == "Bad Endpoint"


def test_disabled_endpoint_missing_identity_mapping_is_ignored(db_session):
    """Disabled endpoint with no identity mapping is ignored — connector is valid."""
    _make_connector(db_session, "conn-disabled")
    _make_endpoint(db_session, "conn-disabled", "ep-disabled", name="Disabled", is_enabled=False)
    # No identity mapping for the disabled endpoint
    _make_mapping(db_session, "ep-disabled", "map-dis", target_field="operatingSystem")

    is_valid, invalid = validate_endpoint_mappings("conn-disabled", db_session)

    assert is_valid is True
    assert invalid == []
