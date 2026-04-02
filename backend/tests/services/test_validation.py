"""Unit tests for validation service — validate_endpoint_mappings.

Validation now delegates to find_base_endpoint() for canvas-based detection.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
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


def _make_canvas(db, canvas_id, connector_id, is_enabled=True):
    canvas = Canvas(
        id=canvas_id,
        connector_id=connector_id,
        name="Test Canvas",
        is_enabled=is_enabled,
    )
    db.add(canvas)
    db.commit()
    return canvas


def _make_canvas_endpoint(db, ce_id, canvas_id, endpoint_id, parent_ref_id=None, tree_order=0):
    ce = CanvasEndpoint(
        id=ce_id,
        canvas_id=canvas_id,
        endpoint_id=endpoint_id,
        parent_ref_id=parent_ref_id,
        tree_order=tree_order,
    )
    db.add(ce)
    db.commit()
    return ce


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
    """Connector with no enabled canvases returns (True, []) — guard is in run trigger."""
    _make_connector(db_session, "conn-no-endpoints")

    is_valid, invalid = validate_endpoint_mappings("conn-no-endpoints", db_session)

    assert is_valid is True
    assert invalid == []


def test_canvas_with_identity_mapping_returns_valid(db_session):
    """Canvas with endpoint that has an identity mapping returns valid."""
    _make_connector(db_session, "conn-valid")
    _make_endpoint(db_session, "conn-valid", "ep-valid", is_enabled=True)
    _make_canvas(db_session, "canvas-1", "conn-valid")
    _make_canvas_endpoint(db_session, "ce-1", "canvas-1", "ep-valid")
    _make_mapping(db_session, "ep-valid", "map-1", target_field="hostName")

    is_valid, invalid = validate_endpoint_mappings("conn-valid", db_session, canvas_id="canvas-1")

    assert is_valid is True
    assert invalid == []


def test_canvas_missing_identity_mapping_returns_invalid(db_session):
    """Canvas with endpoint that has no identity mapping returns invalid with error."""
    _make_connector(db_session, "conn-invalid")
    _make_endpoint(db_session, "conn-invalid", "ep-invalid", name="Bad Endpoint", is_enabled=True)
    _make_canvas(db_session, "canvas-1", "conn-invalid")
    _make_canvas_endpoint(db_session, "ce-1", "canvas-1", "ep-invalid")
    _make_mapping(db_session, "ep-invalid", "map-bad", target_field="operatingSystem")

    is_valid, invalid = validate_endpoint_mappings("conn-invalid", db_session, canvas_id="canvas-1")

    assert is_valid is False
    assert len(invalid) == 1
    assert invalid[0]["canvas_id"] == "canvas-1"
    assert "no endpoint has identity fields mapped" in invalid[0]["error"]


def test_disabled_canvas_ignored_in_full_connector_validation(db_session):
    """Disabled canvas is ignored during full connector validation."""
    _make_connector(db_session, "conn-disabled")
    _make_endpoint(db_session, "conn-disabled", "ep-1", is_enabled=True)
    _make_canvas(db_session, "canvas-disabled", "conn-disabled", is_enabled=False)
    _make_canvas_endpoint(db_session, "ce-1", "canvas-disabled", "ep-1")
    # No identity mapping — but canvas is disabled
    _make_mapping(db_session, "ep-1", "map-1", target_field="operatingSystem")

    is_valid, invalid = validate_endpoint_mappings("conn-disabled", db_session)

    assert is_valid is True
    assert invalid == []


def test_full_connector_validation_multiple_canvases(db_session):
    """Full connector validation checks all enabled canvases and collects errors."""
    _make_connector(db_session, "conn-multi")
    _make_endpoint(db_session, "conn-multi", "ep-good")
    _make_endpoint(db_session, "conn-multi", "ep-bad")
    # Canvas 1: valid (has identity mapping)
    _make_canvas(db_session, "canvas-good", "conn-multi")
    _make_canvas_endpoint(db_session, "ce-good", "canvas-good", "ep-good")
    _make_mapping(db_session, "ep-good", "map-good", target_field="hostName")
    # Canvas 2: invalid (no identity mapping)
    _make_canvas(db_session, "canvas-bad", "conn-multi")
    _make_canvas_endpoint(db_session, "ce-bad", "canvas-bad", "ep-bad")
    _make_mapping(db_session, "ep-bad", "map-bad", target_field="operatingSystem")

    is_valid, invalid = validate_endpoint_mappings("conn-multi", db_session)

    assert is_valid is False
    assert len(invalid) == 1
    assert invalid[0]["canvas_id"] == "canvas-bad"
