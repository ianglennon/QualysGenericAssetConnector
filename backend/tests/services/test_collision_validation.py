"""Unit tests for cross-endpoint target field collision validation."""

import pytest

from app.db.base import Base
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.field_mapping import FieldMapping
from app.services.validation import validate_no_target_collisions


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


def _make_canvas(db, connector_id, canvas_id="canvas-1", name="Default Canvas"):
    canvas = Canvas(
        id=canvas_id,
        connector_id=connector_id,
        name=name,
    )
    db.add(canvas)
    db.commit()
    return canvas


def _make_canvas_endpoint(db, canvas_id, endpoint_id, ce_id):
    ce = CanvasEndpoint(
        id=ce_id,
        canvas_id=canvas_id,
        endpoint_id=endpoint_id,
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


def test_no_collisions_different_targets(db_session):
    """Two endpoints with different target fields -> no collisions."""
    _make_connector(db_session, "conn-1")
    _make_endpoint(db_session, "conn-1", "ep-1", name="Nodes")
    _make_endpoint(db_session, "conn-1", "ep-2", name="VMs")
    _make_canvas(db_session, "conn-1", "canvas-1")
    _make_canvas_endpoint(db_session, "canvas-1", "ep-1", "ce-1")
    _make_canvas_endpoint(db_session, "canvas-1", "ep-2", "ce-2")
    _make_mapping(db_session, "ep-1", "m-1", target_field="hostName")
    _make_mapping(db_session, "ep-2", "m-2", target_field="ipAddress")

    result = validate_no_target_collisions("canvas-1", db_session)

    assert result == []


def test_collision_detected_same_target(db_session):
    """Two endpoints map to same target field -> collision reported."""
    _make_connector(db_session, "conn-2")
    _make_endpoint(db_session, "conn-2", "ep-a", name="Nodes")
    _make_endpoint(db_session, "conn-2", "ep-b", name="VMs")
    _make_canvas(db_session, "conn-2", "canvas-2")
    _make_canvas_endpoint(db_session, "canvas-2", "ep-a", "ce-a")
    _make_canvas_endpoint(db_session, "canvas-2", "ep-b", "ce-b")
    _make_mapping(db_session, "ep-a", "m-a1", target_field="hostName")
    _make_mapping(db_session, "ep-b", "m-b1", target_field="hostName")

    result = validate_no_target_collisions("canvas-2", db_session)

    assert len(result) == 1
    assert result[0]["field"] == "hostName"
    assert sorted(result[0]["endpoints"]) == ["Nodes", "VMs"]


def test_same_endpoint_same_target_no_collision(db_session):
    """Same endpoint maps to same target twice -> NOT a cross-endpoint collision."""
    _make_connector(db_session, "conn-3")
    _make_endpoint(db_session, "conn-3", "ep-x", name="Nodes")
    _make_canvas(db_session, "conn-3", "canvas-3")
    _make_canvas_endpoint(db_session, "canvas-3", "ep-x", "ce-x")
    _make_mapping(db_session, "ep-x", "m-x1", target_field="hostName", source_field="name1")
    _make_mapping(db_session, "ep-x", "m-x2", target_field="hostName", source_field="name2")

    result = validate_no_target_collisions("canvas-3", db_session)

    assert result == []


def test_identity_field_collision(db_session):
    """Identity field collision follows same rule (D-02)."""
    _make_connector(db_session, "conn-4")
    _make_endpoint(db_session, "conn-4", "ep-i1", name="Source A")
    _make_endpoint(db_session, "conn-4", "ep-i2", name="Source B")
    _make_canvas(db_session, "conn-4", "canvas-4")
    _make_canvas_endpoint(db_session, "canvas-4", "ep-i1", "ce-i1")
    _make_canvas_endpoint(db_session, "canvas-4", "ep-i2", "ce-i2")
    _make_mapping(db_session, "ep-i1", "m-id1", target_field="instanceUuid")
    _make_mapping(db_session, "ep-i2", "m-id2", target_field="instanceUuid")

    result = validate_no_target_collisions("canvas-4", db_session)

    assert len(result) == 1
    assert result[0]["field"] == "instanceUuid"
    assert sorted(result[0]["endpoints"]) == ["Source A", "Source B"]


def test_three_endpoints_one_collision_pair(db_session):
    """Three endpoints, only two collide -> only colliding field returned."""
    _make_connector(db_session, "conn-5")
    _make_endpoint(db_session, "conn-5", "ep-t1", name="Alpha")
    _make_endpoint(db_session, "conn-5", "ep-t2", name="Beta")
    _make_endpoint(db_session, "conn-5", "ep-t3", name="Gamma")
    _make_canvas(db_session, "conn-5", "canvas-5")
    _make_canvas_endpoint(db_session, "canvas-5", "ep-t1", "ce-t1")
    _make_canvas_endpoint(db_session, "canvas-5", "ep-t2", "ce-t2")
    _make_canvas_endpoint(db_session, "canvas-5", "ep-t3", "ce-t3")
    _make_mapping(db_session, "ep-t1", "m-t1", target_field="hostName")
    _make_mapping(db_session, "ep-t2", "m-t2", target_field="hostName")
    _make_mapping(db_session, "ep-t3", "m-t3", target_field="ipAddress")

    result = validate_no_target_collisions("canvas-5", db_session)

    assert len(result) == 1
    assert result[0]["field"] == "hostName"
    assert sorted(result[0]["endpoints"]) == ["Alpha", "Beta"]


def test_canvas_with_no_endpoints(db_session):
    """Canvas with no endpoints -> no collisions."""
    _make_connector(db_session, "conn-6")
    _make_canvas(db_session, "conn-6", "canvas-6")

    result = validate_no_target_collisions("canvas-6", db_session)

    assert result == []
