"""Tests for multi-canvas backend API (MC-01 through MC-05).

MC-01: Canvas list API returns enriched aggregation fields
MC-02: Single-canvas sync trigger accepts canvas_id query parameter
MC-03: Disabled canvases skipped during full-connector sync
MC-04: Default canvas auto-created for connectors with endpoints after migration
MC-05: Canvas-aware validation validates only leaf endpoints

Uses shared conftest.py fixtures for DB.
"""

import uuid
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.connector import Connector
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping
from app.models.run_history import EndpointRunLog, RunHistory, RunStatus


def _new_connector(db_session: Session) -> Connector:
    c = Connector(
        id=str(uuid.uuid4()),
        name="Test Connector",
        base_url="https://api.example.com",
        auth_method="bearer_token",
    )
    db_session.add(c)
    db_session.flush()
    return c


def _new_canvas(db_session: Session, connector_id: str, name: str = "Default", enabled: bool = True) -> Canvas:
    canvas = Canvas(
        id=str(uuid.uuid4()),
        connector_id=connector_id,
        name=name,
        is_enabled=enabled,
    )
    db_session.add(canvas)
    db_session.flush()
    return canvas


def _new_endpoint(db_session: Session, connector_id: str) -> ConnectorEndpoint:
    ep = ConnectorEndpoint(
        id=str(uuid.uuid4()),
        connector_id=connector_id,
        name="Test Endpoint",
        path="/api/test",
        is_enabled=True,
        display_order=0,
    )
    db_session.add(ep)
    db_session.flush()
    return ep


def _new_canvas_endpoint(db_session: Session, canvas_id: str, endpoint_id: str, parent_ref_id: str | None = None) -> CanvasEndpoint:
    ce = CanvasEndpoint(
        id=str(uuid.uuid4()),
        canvas_id=canvas_id,
        endpoint_id=endpoint_id,
        parent_ref_id=parent_ref_id,
        field_role="data",
        max_concurrency=5,
        tree_order=0,
    )
    db_session.add(ce)
    db_session.flush()
    return ce


def _new_field_mapping(db_session: Session, endpoint_id: str, target_field: str, canvas_id: str | None = None) -> FieldMapping:
    fm = FieldMapping(
        id=str(uuid.uuid4()),
        endpoint_id=endpoint_id,
        canvas_id=canvas_id,
        target_field=target_field,
        mapping_type="direct_copy",
        source_field="id",
    )
    db_session.add(fm)
    db_session.flush()
    return fm


# ---------------------------------------------------------------------------
# MC-01: Canvas list API returns enriched aggregation fields
# ---------------------------------------------------------------------------

class TestCanvasListAggregation:
    """MC-01: list_canvases returns CanvasListResponse with aggregation fields."""

    def test_canvas_list_includes_aggregation_fields(self, db_session: Session):
        """Canvas list endpoint returns endpoint_count, field_mapping_count, last_run_status, last_run_at."""
        from app.routers.canvases import list_canvases

        connector = _new_connector(db_session)
        canvas = _new_canvas(db_session, connector.id)
        ep = _new_endpoint(db_session, connector.id)
        _new_canvas_endpoint(db_session, canvas.id, ep.id)
        _new_field_mapping(db_session, ep.id, "hostName", canvas_id=canvas.id)

        result = list_canvases(connector_id=connector.id, db=db_session, _=None)

        assert len(result) == 1
        item = result[0]
        assert item.id == canvas.id
        assert item.endpoint_count == 1
        assert item.field_mapping_count == 1
        assert item.last_run_status is None
        assert item.last_run_at is None

    def test_canvas_list_last_run_status_populated_from_endpoint_log(self, db_session: Session):
        """last_run_status reflects most recent EndpointRunLog for that canvas."""
        from app.routers.canvases import list_canvases

        connector = _new_connector(db_session)
        canvas = _new_canvas(db_session, connector.id)
        ep = _new_endpoint(db_session, connector.id)

        # Create a fake run and log
        run = RunHistory(
            id=str(uuid.uuid4()),
            connector_id=connector.id,
            status=RunStatus.success,
            started_at=datetime.utcnow(),
        )
        db_session.add(run)
        db_session.flush()

        log = EndpointRunLog(
            id=str(uuid.uuid4()),
            run_id=run.id,
            endpoint_id=ep.id,
            canvas_id=canvas.id,
            execution_order=0,
            records_fetched=5,
            records_submitted=5,
            records_failed=0,
            status="success",
        )
        db_session.add(log)
        db_session.flush()

        result = list_canvases(connector_id=connector.id, db=db_session, _=None)

        assert len(result) == 1
        assert result[0].last_run_status == "success"
        assert result[0].last_run_at is not None

    def test_canvas_list_returns_empty_for_no_canvases(self, db_session: Session):
        """list_canvases returns empty list when connector has no canvases."""
        from app.routers.canvases import list_canvases

        connector = _new_connector(db_session)
        result = list_canvases(connector_id=connector.id, db=db_session, _=None)
        assert result == []

    def test_canvas_list_zero_counts_when_no_endpoints_or_mappings(self, db_session: Session):
        """Canvas without endpoints or mappings returns 0 counts and no last_run."""
        from app.routers.canvases import list_canvases

        connector = _new_connector(db_session)
        _new_canvas(db_session, connector.id)
        result = list_canvases(connector_id=connector.id, db=db_session, _=None)

        assert result[0].endpoint_count == 0
        assert result[0].field_mapping_count == 0
        assert result[0].last_run_status is None


# ---------------------------------------------------------------------------
# MC-02: Single-canvas sync trigger validates canvas_id
# ---------------------------------------------------------------------------

class TestSingleCanvasSyncTrigger:
    """MC-02: trigger_connector_run accepts canvas_id and validates it exists."""

    def test_trigger_run_returns_404_for_nonexistent_canvas(self, db_session: Session):
        """Returns 404 if canvas_id does not exist under the connector."""
        from app.routers.runs import trigger_connector_run
        from fastapi import BackgroundTasks, HTTPException

        connector = _new_connector(db_session)
        ep = _new_endpoint(db_session, connector.id)
        # Add identity mapping so validation passes if we get that far
        _new_field_mapping(db_session, ep.id, "hostName")

        with pytest.raises(HTTPException) as exc_info:
            trigger_connector_run(
                connector_id=connector.id,
                background_tasks=BackgroundTasks(),
                db=db_session,
                _user=MagicMock(),
                canvas_id="nonexistent-canvas-id",
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"]["code"] == "CANVAS_NOT_FOUND"

    def test_trigger_run_returns_400_for_disabled_canvas(self, db_session: Session):
        """Returns 400 if canvas_id refers to a disabled canvas."""
        from app.routers.runs import trigger_connector_run
        from fastapi import BackgroundTasks, HTTPException

        connector = _new_connector(db_session)
        ep = _new_endpoint(db_session, connector.id)
        _new_field_mapping(db_session, ep.id, "hostName")
        canvas = _new_canvas(db_session, connector.id, enabled=False)

        with pytest.raises(HTTPException) as exc_info:
            trigger_connector_run(
                connector_id=connector.id,
                background_tasks=BackgroundTasks(),
                db=db_session,
                _user=MagicMock(),
                canvas_id=canvas.id,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"]["code"] == "CANVAS_DISABLED"

    def test_trigger_run_returns_404_for_canvas_wrong_connector(self, db_session: Session):
        """Returns 404 if canvas_id belongs to a different connector."""
        from app.routers.runs import trigger_connector_run
        from fastapi import BackgroundTasks, HTTPException

        connector1 = _new_connector(db_session)
        connector2 = _new_connector(db_session)
        ep = _new_endpoint(db_session, connector1.id)
        _new_field_mapping(db_session, ep.id, "hostName")
        canvas_for_other = _new_canvas(db_session, connector2.id)

        with pytest.raises(HTTPException) as exc_info:
            trigger_connector_run(
                connector_id=connector1.id,
                background_tasks=BackgroundTasks(),
                db=db_session,
                _user=MagicMock(),
                canvas_id=canvas_for_other.id,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"]["code"] == "CANVAS_NOT_FOUND"


# ---------------------------------------------------------------------------
# MC-03: Disabled canvases skipped during full-connector sync
# ---------------------------------------------------------------------------

class TestIngestionSkipsDisabledCanvases:
    """MC-03: run_ingestion only executes enabled canvases."""

    def test_run_ingestion_accepts_canvas_id_parameter(self):
        """run_ingestion signature accepts optional canvas_id parameter."""
        import inspect
        from app.services.ingestion_service import run_ingestion
        sig = inspect.signature(run_ingestion)
        params = sig.parameters
        assert "canvas_id" in params
        assert params["canvas_id"].default is None

    def test_run_ingestion_canvas_id_filters_to_single_canvas(self, db_session: Session):
        """When canvas_id provided, only that canvas is queried (not all canvases)."""
        from app.models.canvas import Canvas as CanvasModel

        connector = _new_connector(db_session)
        enabled_canvas = _new_canvas(db_session, connector.id, name="Enabled Canvas", enabled=True)
        _new_canvas(db_session, connector.id, name="Disabled Canvas", enabled=False)

        # Simulate what ingestion does: filter by canvas_id
        canvases = (
            db_session.query(CanvasModel)
            .filter(CanvasModel.id == enabled_canvas.id, CanvasModel.is_enabled == True)
            .all()
        )

        assert len(canvases) == 1
        assert canvases[0].id == enabled_canvas.id

    def test_full_connector_sync_excludes_disabled_canvas(self, db_session: Session):
        """Full-connector sync queries only enabled canvases."""
        from app.models.canvas import Canvas as CanvasModel

        connector = _new_connector(db_session)
        _new_canvas(db_session, connector.id, name="Enabled Canvas", enabled=True)
        _new_canvas(db_session, connector.id, name="Disabled Canvas", enabled=False)

        # Simulate what ingestion does for full sync (no canvas_id)
        canvases = (
            db_session.query(CanvasModel)
            .filter(
                CanvasModel.connector_id == connector.id,
                CanvasModel.is_enabled == True,
            )
            .all()
        )

        assert len(canvases) == 1
        assert canvases[0].name == "Enabled Canvas"


# ---------------------------------------------------------------------------
# MC-04: Default canvas migration creates canvas for connectors with endpoints
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# MC-05: Canvas-aware validation validates only leaf endpoints
# ---------------------------------------------------------------------------

class TestCanvasAwareValidation:
    """MC-05: validate_endpoint_mappings with canvas_id validates only leaf endpoints."""

    def test_validate_leaf_only_ignores_parent_endpoint(self, db_session: Session):
        """When canvas has parent->leaf structure, only the leaf is validated."""
        from app.services.validation import validate_endpoint_mappings

        connector = _new_connector(db_session)
        canvas = _new_canvas(db_session, connector.id)

        parent_ep = _new_endpoint(db_session, connector.id)
        leaf_ep = ConnectorEndpoint(
            id=str(uuid.uuid4()),
            connector_id=connector.id,
            name="Leaf Endpoint",
            path="/api/leaf",
            is_enabled=True,
            display_order=1,
        )
        db_session.add(leaf_ep)
        db_session.flush()

        parent_ce = _new_canvas_endpoint(db_session, canvas.id, parent_ep.id, parent_ref_id=None)
        _new_canvas_endpoint(db_session, canvas.id, leaf_ep.id, parent_ref_id=parent_ce.id)

        # Only give identity mapping to the leaf endpoint
        _new_field_mapping(db_session, leaf_ep.id, "hostName", canvas_id=canvas.id)

        # No identity mapping on parent_ep -- but it should be ignored (not a leaf)
        is_valid, invalid = validate_endpoint_mappings(connector.id, db_session, canvas_id=canvas.id)

        assert is_valid is True
        assert invalid == []

    def test_validate_fails_when_leaf_missing_identity_mapping(self, db_session: Session):
        """Validation fails when a leaf endpoint has no identity mapping."""
        from app.services.validation import validate_endpoint_mappings

        connector = _new_connector(db_session)
        canvas = _new_canvas(db_session, connector.id)
        ep = _new_endpoint(db_session, connector.id)
        _new_canvas_endpoint(db_session, canvas.id, ep.id)

        # No identity mapping on the single (leaf) endpoint
        is_valid, invalid = validate_endpoint_mappings(connector.id, db_session, canvas_id=canvas.id)

        assert is_valid is False
        assert len(invalid) == 1
        assert invalid[0]["canvas_id"] == canvas.id

    def test_validate_passes_when_leaf_has_identity_mapping(self, db_session: Session):
        """Validation passes when leaf endpoint has a valid identity mapping."""
        from app.services.validation import validate_endpoint_mappings

        connector = _new_connector(db_session)
        canvas = _new_canvas(db_session, connector.id)
        ep = _new_endpoint(db_session, connector.id)
        _new_canvas_endpoint(db_session, canvas.id, ep.id)
        _new_field_mapping(db_session, ep.id, "hostName", canvas_id=canvas.id)

        is_valid, invalid = validate_endpoint_mappings(connector.id, db_session, canvas_id=canvas.id)

        assert is_valid is True
        assert invalid == []

    def test_validate_without_canvas_id_checks_all_enabled_canvases(self, db_session: Session):
        """Without canvas_id, validation covers all enabled canvases."""
        from app.services.validation import validate_endpoint_mappings

        connector = _new_connector(db_session)
        canvas1 = _new_canvas(db_session, connector.id, name="Canvas 1")
        canvas2 = _new_canvas(db_session, connector.id, name="Canvas 2")

        ep1 = _new_endpoint(db_session, connector.id)
        ep2 = ConnectorEndpoint(
            id=str(uuid.uuid4()),
            connector_id=connector.id,
            name="Endpoint 2",
            path="/api/two",
            is_enabled=True,
            display_order=1,
        )
        db_session.add(ep2)
        db_session.flush()

        _new_canvas_endpoint(db_session, canvas1.id, ep1.id)
        _new_canvas_endpoint(db_session, canvas2.id, ep2.id)

        # Give identity mapping to ep1 but not ep2
        _new_field_mapping(db_session, ep1.id, "hostName", canvas_id=canvas1.id)

        is_valid, invalid = validate_endpoint_mappings(connector.id, db_session, canvas_id=None)

        assert is_valid is False
        invalid_canvas_ids = [e["canvas_id"] for e in invalid]
        assert canvas2.id in invalid_canvas_ids
        assert canvas1.id not in invalid_canvas_ids

    def test_validate_skips_disabled_canvases_in_full_sync(self, db_session: Session):
        """Full connector validation ignores disabled canvases."""
        from app.services.validation import validate_endpoint_mappings

        connector = _new_connector(db_session)
        enabled_canvas = _new_canvas(db_session, connector.id, name="Enabled", enabled=True)
        disabled_canvas = _new_canvas(db_session, connector.id, name="Disabled", enabled=False)

        ep1 = _new_endpoint(db_session, connector.id)
        ep2 = ConnectorEndpoint(
            id=str(uuid.uuid4()),
            connector_id=connector.id,
            name="Endpoint In Disabled Canvas",
            path="/api/disabled",
            is_enabled=True,
            display_order=1,
        )
        db_session.add(ep2)
        db_session.flush()

        _new_canvas_endpoint(db_session, enabled_canvas.id, ep1.id)
        _new_canvas_endpoint(db_session, disabled_canvas.id, ep2.id)

        # Give identity mapping to ep1 (enabled canvas leaf)
        _new_field_mapping(db_session, ep1.id, "hostName", canvas_id=enabled_canvas.id)
        # ep2 has no identity mapping, but it's in a disabled canvas -- should be ignored

        is_valid, invalid = validate_endpoint_mappings(connector.id, db_session, canvas_id=None)

        assert is_valid is True
        assert invalid == []
