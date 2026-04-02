"""Integration test: collision validation wired into batch_replace_endpoint_mappings().

Gap 59-02-02: Verifies that saving mappings that create cross-endpoint target field
collisions in the same canvas causes batch_replace_endpoint_mappings() to return
is_valid_mappings=False with collision errors in validation_errors.

Approach: Call batch_replace_endpoint_mappings() directly as a Python function
(bypassing HTTP layer) to avoid the Alembic-vs-create_all conflict present in the
test infrastructure when using TestClient.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.db.base import Base
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.field_mapping import FieldMapping
from app.schemas.field_mapping import BatchReplaceRequest, FieldMappingCreate
from app.routers.field_mappings import batch_replace_endpoint_mappings


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def _setup_connector_with_two_endpoints_in_canvas(db):
    """Create connector + two endpoints + canvas + canvas endpoints + ep1 hostName mapping.

    Returns (connector_id, ep1_id, ep2_id).
    """
    conn_id = str(uuid.uuid4())
    ep1_id = str(uuid.uuid4())
    ep2_id = str(uuid.uuid4())
    canvas_id = str(uuid.uuid4())
    ce1_id = str(uuid.uuid4())
    ce2_id = str(uuid.uuid4())

    connector = Connector(
        id=conn_id,
        name="Collision Test Connector",
        base_url="https://collision-test.example.com",
        auth_method="bearer_token",
    )
    db.add(connector)

    ep1 = ConnectorEndpoint(
        id=ep1_id,
        connector_id=conn_id,
        name="Nodes Endpoint",
        path="/nodes",
        is_enabled=True,
        display_order=0,
    )
    db.add(ep1)

    ep2 = ConnectorEndpoint(
        id=ep2_id,
        connector_id=conn_id,
        name="VMs Endpoint",
        path="/vms",
        is_enabled=True,
        display_order=1,
    )
    db.add(ep2)

    canvas = Canvas(
        id=canvas_id,
        connector_id=conn_id,
        name="Test Canvas",
    )
    db.add(canvas)
    db.commit()

    ce1 = CanvasEndpoint(
        id=ce1_id,
        canvas_id=canvas_id,
        endpoint_id=ep1_id,
        tree_order=0,
    )
    db.add(ce1)

    ce2 = CanvasEndpoint(
        id=ce2_id,
        canvas_id=canvas_id,
        endpoint_id=ep2_id,
        parent_ref_id=ce1_id,
        tree_order=1,
    )
    db.add(ce2)

    # Pre-seed ep1 with a conflicting mapping (hostName)
    existing_mapping = FieldMapping(
        id=str(uuid.uuid4()),
        endpoint_id=ep1_id,
        mapping_type="direct_copy",
        target_field="hostName",
        source_field="name",
    )
    db.add(existing_mapping)
    db.commit()

    return conn_id, ep1_id, ep2_id


def test_collision_wired_into_batch_replace_sets_is_valid_mappings_false(db_session):
    """batch_replace_endpoint_mappings sets is_valid_mappings=False when cross-endpoint
    collision exists in a shared canvas.

    Arrange:
    - Connector with two endpoints (ep1, ep2) in the same canvas
    - ep1 already has hostName mapped
    Action:
    - Call batch_replace_endpoint_mappings for ep2 with hostName (creating a collision)
    Assert:
    - Response.is_valid_mappings is False
    - Response.validation_errors contains message about "hostName" mapped on multiple endpoints
    """
    conn_id, ep1_id, ep2_id = _setup_connector_with_two_endpoints_in_canvas(db_session)

    payload = BatchReplaceRequest(
        mappings=[
            FieldMappingCreate(
                mapping_type="direct_copy",
                target_field="hostName",  # collision: ep1 already maps this
                source_field="vm_name",
                order=0,
            )
        ]
    )

    response = batch_replace_endpoint_mappings(
        connector_id=conn_id,
        endpoint_id=ep2_id,
        payload=payload,
        db=db_session,
    )

    assert response.is_valid_mappings is False, (
        f"Expected is_valid_mappings=False for cross-endpoint collision, "
        f"got {response.is_valid_mappings}. validation_errors={response.validation_errors}"
    )

    # At least one error message must name the conflicting field
    collision_errors = [e for e in response.validation_errors if "hostName" in e]
    assert collision_errors, (
        f"Expected a validation_error mentioning 'hostName', "
        f"but got: {response.validation_errors}"
    )

    # Error message must name both endpoints
    assert any(
        "Nodes Endpoint" in e or "VMs Endpoint" in e for e in collision_errors
    ), (
        f"Expected collision error to name endpoints, got: {collision_errors}"
    )


def test_no_collision_batch_replace_does_not_produce_false_positive(db_session):
    """batch_replace_endpoint_mappings does NOT produce collision errors when
    endpoints map different target fields.

    Verifies the collision check does not produce false positives.
    """
    conn_id, ep1_id, ep2_id = _setup_connector_with_two_endpoints_in_canvas(db_session)

    payload = BatchReplaceRequest(
        mappings=[
            FieldMappingCreate(
                mapping_type="direct_copy",
                target_field="ipAddress",  # different from ep1's hostName — no collision
                source_field="ip",
                order=0,
            )
        ]
    )

    response = batch_replace_endpoint_mappings(
        connector_id=conn_id,
        endpoint_id=ep2_id,
        payload=payload,
        db=db_session,
    )

    # No collision — ep1 has hostName (identity), ep2 now has ipAddress — should be valid
    assert response.is_valid_mappings is True, (
        f"Expected is_valid_mappings=True for non-colliding mapping, "
        f"got {response.is_valid_mappings}. validation_errors={response.validation_errors}"
    )

    collision_errors = [e for e in response.validation_errors if "Target field" in e]
    assert collision_errors == [], (
        f"Expected no collision errors but got: {collision_errors}"
    )
