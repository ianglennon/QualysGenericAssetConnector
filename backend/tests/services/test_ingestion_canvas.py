"""Tests for _run_canvas base-aware wiring (Phase 58).

Verifies that _preload_endpoint_mappings correctly loads and converts field
mappings, and that _run_canvas passes base-aware params to execute_tree.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from sqlalchemy.orm import sessionmaker

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
def _patch_session(monkeypatch, engine):
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr("app.services.ingestion_service.SessionLocal", TestSession)


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
    @patch("app.services.ingestion_service.find_base_endpoint")
    async def test_run_canvas_legacy_when_no_base(
        self, mock_find_base, mock_fetch, mock_execute_tree, mock_submit, db_session
    ):
        """Legacy canvas (no base_canvas_endpoint_id) auto-migrates via find_base_endpoint.

        Phase 59 added D-09 auto-migration: when canvas.base_canvas_endpoint_id is None,
        _run_canvas calls find_base_endpoint. If detection succeeds, the detected
        base_canvas_endpoint_id is passed to execute_tree (not None). This test verifies
        that the legacy canvas path still results in a successful execute_tree call after
        auto-migration.
        """
        from app.services.detection import BaseDetectionResult

        connector = _seed_connector(db_session)
        ep_root = _seed_endpoint(db_session, connector.id, "/nodes", 0)
        canvas = _seed_canvas(db_session, connector.id)
        ce_root = _seed_canvas_endpoint(db_session, canvas.id, ep_root.id, tree_order=0)

        # Canvas does NOT have base_canvas_endpoint_id set (legacy state)
        # Phase 59 D-09: auto-migration will call find_base_endpoint and use its result
        mock_find_base.return_value = BaseDetectionResult(
            is_valid=True,
            base_canvas_endpoint_id=ce_root.id,
        )

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

        # D-09: auto-migration should have been attempted
        mock_find_base.assert_called_once_with(canvas.id, db_session)

        # execute_tree should be called with the auto-detected base_canvas_endpoint_id
        mock_execute_tree.assert_called_once()
        call_kwargs = mock_execute_tree.call_args.kwargs
        assert call_kwargs["base_canvas_endpoint_id"] == ce_root.id, (
            "After D-09 auto-migration, execute_tree must receive the detected "
            "base_canvas_endpoint_id, not None"
        )
        # mappings_by_ce should still be passed
        assert isinstance(call_kwargs["mappings_by_ce"], dict)


class TestEnrichmentGapStatusPropagation:
    """Tests that enrichment_gaps > 0 propagates to root_log.status."""

    @pytest.mark.asyncio
    @patch("app.services.ingestion_service.submit_batch")
    @patch("app.services.ingestion_service.execute_tree")
    @patch("app.services.ingestion_service.fetch_all_pages")
    async def test_enrichment_gaps_set_root_log_partial_success(
        self, mock_fetch, mock_execute_tree, mock_submit, db_session
    ):
        """When base_ce_id is set and enrichment_gaps > 0, root_log.status = partial_success."""
        connector = _seed_connector(db_session)
        ep_root = _seed_endpoint(db_session, connector.id, "/nodes", 0)
        canvas = _seed_canvas(db_session, connector.id)
        ce_root = _seed_canvas_endpoint(db_session, canvas.id, ep_root.id, tree_order=0)

        # Simulate Phase 57: set base_canvas_endpoint_id on canvas
        canvas.base_canvas_endpoint_id = ce_root.id

        # Create a mapping so submission path is exercised
        _seed_mapping(db_session, ep_root.id, "hostname", "hostName")

        run = _seed_run(db_session, connector.id)

        mock_fetch.return_value = SourceFetchResult(
            records=[{"hostname": "test-host"}],
            records_fetched=1,
            pages_fetched=1,
            partial=False,
        )

        mock_execute_tree.return_value = FanOutResult(
            enrichment_gaps=2,
            has_failures=True,
            merged_records=[{"hostName": "test"}],
            record_outputs=[],
            base_records_total=1,
            base_records_excluded=0,
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

        # Find root_log (execution_order=0)
        root_log = next(l for l in logs if l.execution_order == 0)
        assert root_log.status == "partial_success", (
            f"Expected root_log.status='partial_success' but got '{root_log.status}'"
        )

        # Verify _rollup_status would produce partial_success
        from app.services.ingestion_service import _rollup_status
        assert _rollup_status(logs) == RunStatus.partial_success

    @pytest.mark.asyncio
    @patch("app.services.ingestion_service.submit_batch")
    @patch("app.services.ingestion_service.execute_tree")
    @patch("app.services.ingestion_service.fetch_all_pages")
    async def test_no_enrichment_gaps_keeps_root_log_success(
        self, mock_fetch, mock_execute_tree, mock_submit, db_session
    ):
        """When base_ce_id is set and enrichment_gaps == 0, root_log.status stays success."""
        connector = _seed_connector(db_session)
        ep_root = _seed_endpoint(db_session, connector.id, "/nodes", 0)
        canvas = _seed_canvas(db_session, connector.id)
        ce_root = _seed_canvas_endpoint(db_session, canvas.id, ep_root.id, tree_order=0)

        # Simulate Phase 57: set base_canvas_endpoint_id on canvas
        canvas.base_canvas_endpoint_id = ce_root.id

        _seed_mapping(db_session, ep_root.id, "hostname", "hostName")

        run = _seed_run(db_session, connector.id)

        mock_fetch.return_value = SourceFetchResult(
            records=[{"hostname": "test-host"}],
            records_fetched=1,
            pages_fetched=1,
            partial=False,
        )

        mock_execute_tree.return_value = FanOutResult(
            enrichment_gaps=0,
            has_failures=False,
            merged_records=[{"hostName": "test"}],
            record_outputs=[],
            base_records_total=1,
            base_records_excluded=0,
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

        # Find root_log (execution_order=0)
        root_log = next(l for l in logs if l.execution_order == 0)
        assert root_log.status == "success", (
            f"Expected root_log.status='success' but got '{root_log.status}'"
        )
