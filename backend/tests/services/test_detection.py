"""Unit tests for base endpoint detection -- find_base_endpoint()."""

import pytest

from app.db.base import Base
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.field_mapping import FieldMapping
from app.services.detection import find_base_endpoint, BaseDetectionResult
from app.services.validation import IDENTITY_ATTRIBUTES


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


def _make_endpoint(db, connector_id, endpoint_id, name="Endpoint 1"):
    endpoint = ConnectorEndpoint(
        id=endpoint_id,
        connector_id=connector_id,
        name=name,
        path="/api/resources",
    )
    db.add(endpoint)
    db.commit()
    return endpoint


def _make_canvas(db, canvas_id, connector_id):
    canvas = Canvas(
        id=canvas_id,
        connector_id=connector_id,
        name="Test Canvas",
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


def test_single_endpoint_with_identity_returns_valid(db_session):
    """Single-endpoint canvas with identity mapping returns is_valid=True,
    base_canvas_endpoint_id = that endpoint's canvas-endpoint ID."""
    _make_connector(db_session)
    _make_endpoint(db_session, "connector-1", "ep-1")
    _make_canvas(db_session, "canvas-1", "connector-1")
    _make_canvas_endpoint(db_session, "ce-1", "canvas-1", "ep-1")
    _make_mapping(db_session, "ep-1", "map-1", target_field="hostName")

    result = find_base_endpoint("canvas-1", db_session)

    assert result.is_valid is True
    assert result.base_canvas_endpoint_id == "ce-1"
    assert result.error_message is None
    assert result.ambiguous_endpoints == []


def test_single_endpoint_no_identity_returns_invalid(db_session):
    """Single-endpoint canvas with no identity mapping returns is_valid=False,
    error_message contains 'no endpoint has identity fields mapped' and lists identity field names."""
    _make_connector(db_session)
    _make_endpoint(db_session, "connector-1", "ep-1")
    _make_canvas(db_session, "canvas-1", "connector-1")
    _make_canvas_endpoint(db_session, "ce-1", "canvas-1", "ep-1")
    _make_mapping(db_session, "ep-1", "map-1", target_field="operatingSystem")

    result = find_base_endpoint("canvas-1", db_session)

    assert result.is_valid is False
    assert result.base_canvas_endpoint_id is None
    assert "no endpoint has identity fields mapped" in result.error_message
    # Check that identity field names are listed
    assert "hostName" in result.error_message
    assert "ipAddress" in result.error_message


def test_three_level_tree_mid_has_identity_returns_mid(db_session):
    """Three-level tree (root -> mid -> leaf) where mid has identity fields
    returns mid as base (per D-01 BFS)."""
    _make_connector(db_session)
    _make_endpoint(db_session, "connector-1", "ep-root", name="Root")
    _make_endpoint(db_session, "connector-1", "ep-mid", name="Mid")
    _make_endpoint(db_session, "connector-1", "ep-leaf", name="Leaf")
    _make_canvas(db_session, "canvas-1", "connector-1")
    _make_canvas_endpoint(db_session, "ce-root", "canvas-1", "ep-root", tree_order=0)
    _make_canvas_endpoint(db_session, "ce-mid", "canvas-1", "ep-mid", parent_ref_id="ce-root", tree_order=0)
    _make_canvas_endpoint(db_session, "ce-leaf", "canvas-1", "ep-leaf", parent_ref_id="ce-mid", tree_order=0)
    # Only mid has identity mapping
    _make_mapping(db_session, "ep-mid", "map-mid", target_field="sourceNativeKey")
    _make_mapping(db_session, "ep-root", "map-root", target_field="operatingSystem")
    _make_mapping(db_session, "ep-leaf", "map-leaf", target_field="operatingSystem")

    result = find_base_endpoint("canvas-1", db_session)

    assert result.is_valid is True
    assert result.base_canvas_endpoint_id == "ce-mid"


def test_three_level_tree_only_leaf_returns_leaf(db_session):
    """Three-level tree where only leaf has identity fields returns leaf as base
    (backward compat per D-04)."""
    _make_connector(db_session)
    _make_endpoint(db_session, "connector-1", "ep-root", name="Root")
    _make_endpoint(db_session, "connector-1", "ep-mid", name="Mid")
    _make_endpoint(db_session, "connector-1", "ep-leaf", name="Leaf")
    _make_canvas(db_session, "canvas-1", "connector-1")
    _make_canvas_endpoint(db_session, "ce-root", "canvas-1", "ep-root", tree_order=0)
    _make_canvas_endpoint(db_session, "ce-mid", "canvas-1", "ep-mid", parent_ref_id="ce-root", tree_order=0)
    _make_canvas_endpoint(db_session, "ce-leaf", "canvas-1", "ep-leaf", parent_ref_id="ce-mid", tree_order=0)
    # Only leaf has identity mapping
    _make_mapping(db_session, "ep-leaf", "map-leaf", target_field="fqdn")

    result = find_base_endpoint("canvas-1", db_session)

    assert result.is_valid is True
    assert result.base_canvas_endpoint_id == "ce-leaf"


def test_same_level_ambiguity_returns_invalid(db_session):
    """Two endpoints at same BFS level both with identity fields returns
    is_valid=False, ambiguous_endpoints has 2 entries (per D-03)."""
    _make_connector(db_session)
    _make_endpoint(db_session, "connector-1", "ep-root", name="Root")
    _make_endpoint(db_session, "connector-1", "ep-child-a", name="Child A")
    _make_endpoint(db_session, "connector-1", "ep-child-b", name="Child B")
    _make_canvas(db_session, "canvas-1", "connector-1")
    _make_canvas_endpoint(db_session, "ce-root", "canvas-1", "ep-root", tree_order=0)
    _make_canvas_endpoint(db_session, "ce-a", "canvas-1", "ep-child-a", parent_ref_id="ce-root", tree_order=0)
    _make_canvas_endpoint(db_session, "ce-b", "canvas-1", "ep-child-b", parent_ref_id="ce-root", tree_order=1)
    # Both children have identity mappings
    _make_mapping(db_session, "ep-child-a", "map-a", target_field="hostName")
    _make_mapping(db_session, "ep-child-b", "map-b", target_field="ipAddress")

    result = find_base_endpoint("canvas-1", db_session)

    assert result.is_valid is False
    assert result.base_canvas_endpoint_id is None
    assert "Multiple endpoints at the same tree level have identity fields mapped" in result.error_message
    assert len(result.ambiguous_endpoints) == 2


def test_different_levels_first_wins(db_session):
    """Two endpoints at different BFS levels both with identity fields returns
    first one found (per D-02 silent first-wins)."""
    _make_connector(db_session)
    _make_endpoint(db_session, "connector-1", "ep-root", name="Root")
    _make_endpoint(db_session, "connector-1", "ep-child", name="Child")
    _make_canvas(db_session, "canvas-1", "connector-1")
    _make_canvas_endpoint(db_session, "ce-root", "canvas-1", "ep-root", tree_order=0)
    _make_canvas_endpoint(db_session, "ce-child", "canvas-1", "ep-child", parent_ref_id="ce-root", tree_order=0)
    # Both have identity mappings but root is at a higher BFS level
    _make_mapping(db_session, "ep-root", "map-root", target_field="hostName")
    _make_mapping(db_session, "ep-child", "map-child", target_field="ipAddress")

    result = find_base_endpoint("canvas-1", db_session)

    assert result.is_valid is True
    assert result.base_canvas_endpoint_id == "ce-root"


def test_empty_canvas_returns_invalid(db_session):
    """Empty canvas (no endpoints) returns is_valid=False with no-identity error."""
    _make_connector(db_session)
    _make_canvas(db_session, "canvas-1", "connector-1")

    result = find_base_endpoint("canvas-1", db_session)

    assert result.is_valid is False
    assert result.base_canvas_endpoint_id is None
    assert "no endpoint has identity fields mapped" in result.error_message


def test_tree_order_determines_sibling_order(db_session):
    """tree_order determines sibling order within a BFS level
    (lower tree_order visited first)."""
    _make_connector(db_session)
    _make_endpoint(db_session, "connector-1", "ep-root", name="Root")
    _make_endpoint(db_session, "connector-1", "ep-child-a", name="Child A")
    _make_endpoint(db_session, "connector-1", "ep-child-b", name="Child B")
    _make_canvas(db_session, "canvas-1", "connector-1")
    _make_canvas_endpoint(db_session, "ce-root", "canvas-1", "ep-root", tree_order=0)
    # Child B has lower tree_order, so it should be visited first
    _make_canvas_endpoint(db_session, "ce-b", "canvas-1", "ep-child-b", parent_ref_id="ce-root", tree_order=0)
    _make_canvas_endpoint(db_session, "ce-a", "canvas-1", "ep-child-a", parent_ref_id="ce-root", tree_order=1)
    # Only Child B has identity mapping -- it should be found first due to tree_order
    _make_mapping(db_session, "ep-child-b", "map-b", target_field="hostName")

    result = find_base_endpoint("canvas-1", db_session)

    assert result.is_valid is True
    assert result.base_canvas_endpoint_id == "ce-b"
