"""Phase 59 gap tests for _run_canvas ingestion behavior.

Gap 59-03-01 (D-10): Auto-migration failure path — when find_base_endpoint returns
is_valid=False, _run_canvas returns a fail_log with failure_stage="validation" and
an error message containing "Canvas migration failed:".

Gap 59-03-02: Base-anchored submission loop — when base_ce_id is set and
fan_out_result.record_outputs is populated, assemble_qualys_record is called per
TraversalRecord, payloads are submitted via submit_batch, and root_log.records_submitted
reflects the correct count.
"""

import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock, call

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
from app.models.run_history import EndpointRunLog, RunHistory, RunStatus
from app.services.detection import BaseDetectionResult
from app.services.fan_out_executor import FanOutResult, TraversalRecord
from app.services.ingestion_service import _run_canvas
from app.services.qualys_adapter import QualysSubmitResult
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


def _seed_endpoint(db, connector_id: str, path: str = "/nodes") -> ConnectorEndpoint:
    ep = ConnectorEndpoint(
        connector_id=connector_id,
        name="Nodes",
        path=path,
        is_enabled=True,
        display_order=0,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def _seed_canvas(db, connector_id: str) -> Canvas:
    canvas = Canvas(
        connector_id=connector_id,
        name="Test Canvas",
    )
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


def _seed_canvas_endpoint(db, canvas_id: str, endpoint_id: str) -> CanvasEndpoint:
    ce = CanvasEndpoint(
        canvas_id=canvas_id,
        endpoint_id=endpoint_id,
        tree_order=0,
    )
    db.add(ce)
    db.commit()
    db.refresh(ce)
    return ce


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


# ---------------------------------------------------------------------------
# Gap 59-03-01 D-10: Auto-migration failure path
# ---------------------------------------------------------------------------

class TestAutoMigrationFailurePath:
    """D-10: When legacy canvas has no identity fields, _run_canvas fails with
    an actionable error in the run log."""

    @pytest.mark.asyncio
    @patch("app.services.ingestion_service.find_base_endpoint")
    @patch("app.services.ingestion_service.fetch_all_pages")
    async def test_canvas_migration_fails_when_no_identity_fields(
        self, mock_fetch, mock_find_base, db_session
    ):
        """When find_base_endpoint returns is_valid=False, _run_canvas returns a
        single fail_log with:
        - status="failed"
        - failure_stage="validation"
        - error_message containing "Canvas migration failed:"
        """
        connector = _seed_connector(db_session)
        ep = _seed_endpoint(db_session, connector.id)
        canvas = _seed_canvas(db_session, connector.id)
        ce = _seed_canvas_endpoint(db_session, canvas.id, ep.id)

        # Canvas has no base_canvas_endpoint_id (legacy state)
        assert canvas.base_canvas_endpoint_id is None

        # Detection fails: no identity fields on any endpoint
        mock_find_base.return_value = BaseDetectionResult(
            is_valid=False,
            base_canvas_endpoint_id=None,
            error_message="Canvas cannot execute: no endpoint has identity fields mapped.",
        )

        # Root fetch succeeds (we get records before migration check)
        mock_fetch.return_value = SourceFetchResult(
            records=[{"id": "asset-1"}],
            records_fetched=1,
            pages_fetched=1,
            partial=False,
        )

        run = _seed_run(db_session, connector.id)
        mock_client = AsyncMock()

        logs = await _run_canvas(
            db_session, run, connector, canvas,
            SimpleNamespace(), mock_client, 0,
        )

        # D-10: exactly one fail_log returned
        assert len(logs) == 1, f"Expected 1 fail_log but got {len(logs)}: {logs}"

        fail_log = logs[0]
        assert fail_log.status == "failed", (
            f"Expected status='failed' but got '{fail_log.status}'"
        )
        assert fail_log.failure_stage == "validation", (
            f"Expected failure_stage='validation' but got '{fail_log.failure_stage}'"
        )
        assert "Canvas migration failed:" in (fail_log.error_message or ""), (
            f"Expected error_message to contain 'Canvas migration failed:' "
            f"but got: '{fail_log.error_message}'"
        )

    @pytest.mark.asyncio
    @patch("app.services.ingestion_service.execute_tree")
    @patch("app.services.ingestion_service.find_base_endpoint")
    @patch("app.services.ingestion_service.fetch_all_pages")
    async def test_canvas_migration_skips_fail_when_detection_succeeds(
        self, mock_fetch, mock_find_base, mock_execute_tree, db_session
    ):
        """When find_base_endpoint returns is_valid=True, _run_canvas does NOT
        return a validation fail_log — execution continues normally.

        This is the positive case to confirm D-10 only fires on failure.
        """
        connector = _seed_connector(db_session)
        ep = _seed_endpoint(db_session, connector.id)
        canvas = _seed_canvas(db_session, connector.id)
        ce = _seed_canvas_endpoint(db_session, canvas.id, ep.id)

        # Detection succeeds
        mock_find_base.return_value = BaseDetectionResult(
            is_valid=True,
            base_canvas_endpoint_id=ce.id,
        )

        mock_fetch.return_value = SourceFetchResult(
            records=[{"id": "asset-1"}],
            records_fetched=1,
            pages_fetched=1,
            partial=False,
        )

        mock_execute_tree.return_value = FanOutResult(
            merged_records=[],
            record_outputs=[],
        )

        run = _seed_run(db_session, connector.id)
        mock_client = AsyncMock()

        logs = await _run_canvas(
            db_session, run, connector, canvas,
            SimpleNamespace(), mock_client, 0,
        )

        # No validation fail_log — at least the root_log must be present
        validation_fails = [l for l in logs if l.failure_stage == "validation"]
        assert validation_fails == [], (
            f"Expected no validation fail_log when detection succeeds, "
            f"but got: {validation_fails}"
        )


# ---------------------------------------------------------------------------
# Gap 59-03-02: Base-anchored submission loop
# ---------------------------------------------------------------------------

class TestBaseAnchoredSubmissionLoop:
    """D-07/D-08: When base_ce_id is set and record_outputs is populated,
    assemble_qualys_record is called per TraversalRecord, payloads are submitted
    via submit_batch in batches, and root_log.records_submitted is correct."""

    @pytest.mark.asyncio
    @patch("app.services.ingestion_service.submit_batch")
    @patch("app.services.ingestion_service.assemble_qualys_record")
    @patch("app.services.ingestion_service.execute_tree")
    @patch("app.services.ingestion_service.fetch_all_pages")
    async def test_assemble_called_per_traversal_record_and_submitted(
        self, mock_fetch, mock_execute_tree, mock_assemble, mock_submit, db_session
    ):
        """For each TraversalRecord in record_outputs:
        - assemble_qualys_record is called once per record
        - The assembled payloads are passed to submit_batch
        - root_log.records_submitted == number of submitted records
        """
        connector = _seed_connector(db_session)
        ep = _seed_endpoint(db_session, connector.id)
        canvas = _seed_canvas(db_session, connector.id)
        ce = _seed_canvas_endpoint(db_session, canvas.id, ep.id)

        # Canvas has base_canvas_endpoint_id already set (not a legacy canvas)
        canvas.base_canvas_endpoint_id = ce.id
        db_session.commit()

        # Two traversal records (two base records)
        tr1 = TraversalRecord(
            raw_record={"id": "asset-1"},
            ancestor_context={},
            endpoint_outputs={ce.id: [{"hostName": "host-1"}]},
        )
        tr2 = TraversalRecord(
            raw_record={"id": "asset-2"},
            ancestor_context={},
            endpoint_outputs={ce.id: [{"hostName": "host-2"}]},
        )

        mock_fetch.return_value = SourceFetchResult(
            records=[{"id": "asset-1"}, {"id": "asset-2"}],
            records_fetched=2,
            pages_fetched=1,
            partial=False,
        )

        mock_execute_tree.return_value = FanOutResult(
            record_outputs=[tr1, tr2],
            merged_records=[{"hostName": "host-1"}, {"hostName": "host-2"}],
            base_records_total=2,
            base_records_excluded=0,
            enrichment_gaps=0,
        )

        # assemble returns a non-empty payload for each record
        mock_assemble.side_effect = [
            {"hostName": "host-1"},
            {"hostName": "host-2"},
        ]

        mock_submit.return_value = QualysSubmitResult(
            submitted_count=2,
            failed_count=0,
            failures=[],
        )

        run = _seed_run(db_session, connector.id)
        mock_client = AsyncMock()

        logs = await _run_canvas(
            db_session, run, connector, canvas,
            SimpleNamespace(), mock_client, 0,
        )

        # assemble_qualys_record must be called once per TraversalRecord
        assert mock_assemble.call_count == 2, (
            f"Expected assemble_qualys_record called 2 times, got {mock_assemble.call_count}"
        )

        # Verify calls were for the two traversal records
        call_args_list = mock_assemble.call_args_list
        called_records = [c.args[0] for c in call_args_list]
        assert tr1 in called_records, "TraversalRecord tr1 was not passed to assemble_qualys_record"
        assert tr2 in called_records, "TraversalRecord tr2 was not passed to assemble_qualys_record"

        # submit_batch must have been called with both payloads
        assert mock_submit.call_count >= 1, "submit_batch was never called"
        # The first positional arg to submit_batch is the batch (list of dicts)
        all_submitted = []
        for c in mock_submit.call_args_list:
            batch = c.args[0]
            all_submitted.extend(batch)
        assert {"hostName": "host-1"} in all_submitted, (
            f"Expected payload {{'hostName': 'host-1'}} in submitted batches, got: {all_submitted}"
        )
        assert {"hostName": "host-2"} in all_submitted, (
            f"Expected payload {{'hostName': 'host-2'}} in submitted batches, got: {all_submitted}"
        )

        # root_log.records_submitted must reflect the submission count from submit_batch
        root_log = next((l for l in logs if l.execution_order == 0), None)
        assert root_log is not None, "No root_log (execution_order=0) found in logs"
        assert root_log.records_submitted == 2, (
            f"Expected root_log.records_submitted=2 but got {root_log.records_submitted}"
        )

    @pytest.mark.asyncio
    @patch("app.services.ingestion_service.submit_batch")
    @patch("app.services.ingestion_service.assemble_qualys_record")
    @patch("app.services.ingestion_service.execute_tree")
    @patch("app.services.ingestion_service.fetch_all_pages")
    async def test_empty_assembled_payload_is_not_submitted(
        self, mock_fetch, mock_execute_tree, mock_assemble, mock_submit, db_session
    ):
        """Assembled payloads that are empty dicts are excluded from submission.

        Verifies the `if payload:` guard in the loop.
        """
        connector = _seed_connector(db_session)
        ep = _seed_endpoint(db_session, connector.id)
        canvas = _seed_canvas(db_session, connector.id)
        ce = _seed_canvas_endpoint(db_session, canvas.id, ep.id)

        canvas.base_canvas_endpoint_id = ce.id
        db_session.commit()

        tr1 = TraversalRecord(
            raw_record={"id": "asset-1"},
            ancestor_context={},
            endpoint_outputs={},  # no mappings -> empty payload
        )
        tr2 = TraversalRecord(
            raw_record={"id": "asset-2"},
            ancestor_context={},
            endpoint_outputs={ce.id: [{"hostName": "host-2"}]},
        )

        mock_fetch.return_value = SourceFetchResult(
            records=[{"id": "asset-1"}, {"id": "asset-2"}],
            records_fetched=2,
            pages_fetched=1,
            partial=False,
        )

        mock_execute_tree.return_value = FanOutResult(
            record_outputs=[tr1, tr2],
            merged_records=[{}, {"hostName": "host-2"}],
            base_records_total=2,
            base_records_excluded=0,
            enrichment_gaps=0,
        )

        # tr1 assembles to empty dict (will be skipped), tr2 assembles to a real payload
        mock_assemble.side_effect = [
            {},                       # tr1: empty -> should not be submitted
            {"hostName": "host-2"},   # tr2: real payload
        ]

        mock_submit.return_value = QualysSubmitResult(
            submitted_count=1,
            failed_count=0,
            failures=[],
        )

        run = _seed_run(db_session, connector.id)
        mock_client = AsyncMock()

        logs = await _run_canvas(
            db_session, run, connector, canvas,
            SimpleNamespace(), mock_client, 0,
        )

        # Only 1 non-empty payload should be submitted
        all_submitted = []
        for c in mock_submit.call_args_list:
            batch = c.args[0]
            all_submitted.extend(batch)

        assert {} not in all_submitted, (
            "Empty payload was incorrectly passed to submit_batch"
        )
        assert all_submitted == [{"hostName": "host-2"}], (
            f"Expected only [{{hostName: host-2}}] submitted, got: {all_submitted}"
        )

        root_log = next((l for l in logs if l.execution_order == 0), None)
        assert root_log is not None
        assert root_log.records_submitted == 1, (
            f"Expected root_log.records_submitted=1 but got {root_log.records_submitted}"
        )
