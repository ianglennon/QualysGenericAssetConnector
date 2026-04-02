"""Tests for _run_canvas base-aware wiring (Phase 58).

Verifies that _preload_endpoint_mappings correctly loads and converts field
mappings, and that _run_canvas passes base-aware params to execute_tree.
"""
import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.db.base import Base
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping
from app.models.qualys_config import QualysConfig
from app.models.run_history import EndpointRunLog, RunHistory, RunStatus
from app.schemas.field_mapping import FieldMappingRule
from app.services.credential_crypto import get_crypto
from app.services.fan_out_executor import FanOutResult, LevelStats
from app.services.ingestion_service import _preload_endpoint_mappings, _build_mapping_rules, _run_canvas
from app.services.qualys_adapter import QualysAdapterError, QualysFailure, QualysSubmitResult
from app.services.source_client import SourceFetchResult


@pytest.fixture(autouse=True)
def db_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.services.ingestion_service.SessionLocal", TestSession)
    db = TestSession()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def _seed_connector(db) -> Connector:
    connector = Connector(
        name="Test Connector",
        base_url="https://source.example.com",
        auth_method="bearer_token",
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


def _seed_endpoint(db, connector_id: str, path: str = "/nodes", display_order: int = 0) -> ConnectorEndpoint:
    ep = ConnectorEndpoint(
        connector_id=connector_id,
        name=f"Endpoint {display_order}",
        path=path,
        is_enabled=True,
        display_order=display_order,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def _seed_canvas(db, connector_id: str, name: str = "Test Canvas") -> Canvas:
    canvas = Canvas(
        connector_id=connector_id,
        name=name,
    )
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


def _seed_canvas_endpoint(
    db, canvas_id: str, endpoint_id: str, parent_ref_id=None, tree_order=0
) -> CanvasEndpoint:
    ce = CanvasEndpoint(
        canvas_id=canvas_id,
        endpoint_id=endpoint_id,
        parent_ref_id=parent_ref_id,
        tree_order=tree_order,
    )
    db.add(ce)
    db.commit()
    db.refresh(ce)
    return ce


def _seed_mapping(db, endpoint_id: str, source_field: str, target_field: str) -> FieldMapping:
    fm = FieldMapping(
        endpoint_id=endpoint_id,
        mapping_type="direct_copy",
        source_field=source_field,
        target_field=target_field,
    )
    db.add(fm)
    db.commit()
    db.refresh(fm)
    return fm


def _seed_run(db, connector_id: str) -> RunHistory:
    run = RunHistory(
        connector_id=connector_id,
        status=RunStatus.running,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


class TestPreloadEndpointMappings:
    """Tests for _preload_endpoint_mappings helper."""

    def test_loads_mappings_for_all_canvas_endpoints(self, db_session):
        """Should return a dict keyed by canvas_endpoint_id with FieldMappingRule lists."""
        connector = _seed_connector(db_session)
        ep1 = _seed_endpoint(db_session, connector.id, "/nodes", 0)
        ep2 = _seed_endpoint(db_session, connector.id, "/vms", 1)
        canvas = _seed_canvas(db_session, connector.id)
        ce1 = _seed_canvas_endpoint(db_session, canvas.id, ep1.id, tree_order=0)
        ce2 = _seed_canvas_endpoint(db_session, canvas.id, ep2.id, parent_ref_id=ce1.id, tree_order=1)

        # Create mappings for ep1
        _seed_mapping(db_session, ep1.id, "hostname", "hostName")
        _seed_mapping(db_session, ep1.id, "ip", "ipAddress")
        # Create mapping for ep2
        _seed_mapping(db_session, ep2.id, "vmid", "vmId")

        ep_map = {ep1.id: ep1, ep2.id: ep2}
        result = _preload_endpoint_mappings(db_session, [ce1, ce2], ep_map)

        assert ce1.id in result
        assert ce2.id in result
        assert len(result[ce1.id]) == 2
        assert len(result[ce2.id]) == 1
        # FieldMappingRule is a discriminated union; check via hasattr instead of isinstance
        assert hasattr(result[ce1.id][0], "target_field")
        assert result[ce1.id][0].target_field == "hostName"
        assert result[ce2.id][0].target_field == "vmId"

    def test_missing_connector_endpoint_returns_empty_list(self, db_session):
        """Should return empty rules list when connector endpoint is not in ep_map."""
        connector = _seed_connector(db_session)
        ep = _seed_endpoint(db_session, connector.id, "/nodes")
        canvas = _seed_canvas(db_session, connector.id)
        ce = _seed_canvas_endpoint(db_session, canvas.id, ep.id)

        # ep_map is empty -- simulates missing connector endpoint
        result = _preload_endpoint_mappings(db_session, [ce], {})

        assert ce.id in result
        assert result[ce.id] == []

    def test_empty_canvas_endpoints_returns_empty_dict(self, db_session):
        """Should return empty dict when no canvas endpoints provided."""
        result = _preload_endpoint_mappings(db_session, [], {})
        assert result == {}


class TestRunCanvasBaseAwareWiring:
    """Tests that _run_canvas passes base-aware params to execute_tree."""

    @pytest.mark.asyncio
    @patch("app.services.ingestion_service.submit_batch")
    @patch("app.services.ingestion_service.execute_tree")
    @patch("app.services.ingestion_service.fetch_all_pages")
    async def test_run_canvas_passes_base_params(
        self, mock_fetch, mock_execute_tree, mock_submit, db_session
    ):
        """When canvas has base_canvas_endpoint_id attr, execute_tree receives it."""
        connector = _seed_connector(db_session)
        ep_root = _seed_endpoint(db_session, connector.id, "/nodes", 0)
        canvas = _seed_canvas(db_session, connector.id)
        ce_root = _seed_canvas_endpoint(db_session, canvas.id, ep_root.id, tree_order=0)

        # Simulate Phase 57: set base_canvas_endpoint_id on canvas
        canvas.base_canvas_endpoint_id = ce_root.id

        run = _seed_run(db_session, connector.id)

        mock_fetch.return_value = SourceFetchResult(
            records=[{"hostname": "node1"}],
            records_fetched=1,
            pages_fetched=1,
            partial=False,
        )

        mock_execute_tree.return_value = FanOutResult(
            merged_records=[{"hostname": "node1"}],
        )

        mock_submit.return_value = QualysSubmitResult(
            submitted_count=1,
            failed_count=0,
            failures=[],
        )

        mock_client = AsyncMock()

        logs = await _run_canvas(
            db_session, run, connector, canvas,
            SimpleNamespace(), mock_client, 0,
        )

        # Verify execute_tree was called with base-aware params
        mock_execute_tree.assert_called_once()
        call_kwargs = mock_execute_tree.call_args.kwargs
        assert call_kwargs["base_canvas_endpoint_id"] == ce_root.id
        assert isinstance(call_kwargs["mappings_by_ce"], dict)
        assert ce_root.id in call_kwargs["mappings_by_ce"]

    @pytest.mark.asyncio
    @patch("app.services.ingestion_service.submit_batch")
    @patch("app.services.ingestion_service.execute_tree")
    @patch("app.services.ingestion_service.fetch_all_pages")
    async def test_run_canvas_legacy_when_no_base(
        self, mock_fetch, mock_execute_tree, mock_submit, db_session
    ):
        """When canvas has no base_canvas_endpoint_id, execute_tree gets None."""
        connector = _seed_connector(db_session)
        ep_root = _seed_endpoint(db_session, connector.id, "/nodes", 0)
        canvas = _seed_canvas(db_session, connector.id)
        ce_root = _seed_canvas_endpoint(db_session, canvas.id, ep_root.id, tree_order=0)

        # Canvas does NOT have base_canvas_endpoint_id attribute
        run = _seed_run(db_session, connector.id)

        mock_fetch.return_value = SourceFetchResult(
            records=[{"hostname": "node1"}],
            records_fetched=1,
            pages_fetched=1,
            partial=False,
        )

        mock_execute_tree.return_value = FanOutResult(
            merged_records=[{"hostname": "node1"}],
        )

        mock_submit.return_value = QualysSubmitResult(
            submitted_count=1,
            failed_count=0,
            failures=[],
        )

        mock_client = AsyncMock()

        logs = await _run_canvas(
            db_session, run, connector, canvas,
            SimpleNamespace(), mock_client, 0,
        )

        # Verify execute_tree was called with base_canvas_endpoint_id=None
        mock_execute_tree.assert_called_once()
        call_kwargs = mock_execute_tree.call_args.kwargs
        assert call_kwargs["base_canvas_endpoint_id"] is None
        # mappings_by_ce should still be passed
        assert isinstance(call_kwargs["mappings_by_ce"], dict)
