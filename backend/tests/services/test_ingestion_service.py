import os
from datetime import datetime
from unittest.mock import AsyncMock, patch

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
from app.services.credential_crypto import get_crypto
from app.services.fan_out_executor import FanOutResult, LevelStats
from app.services.ingestion_service import _run_canvas, run_ingestion
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


def _seed_endpoint(db, connector_id: str, path: str = "/assets", display_order: int = 0, is_enabled: bool = True) -> ConnectorEndpoint:
    endpoint = ConnectorEndpoint(
        connector_id=connector_id,
        name=f"Endpoint {display_order}",
        path=path,
        is_enabled=is_enabled,
        display_order=display_order,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


def _seed_mapping(db, endpoint_id: str) -> FieldMapping:
    mapping = FieldMapping(
        endpoint_id=endpoint_id,
        target_field="name",
        mapping_type="direct_copy",
        source_field="hostname",
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def _seed_qualys_config(db) -> QualysConfig:
    crypto = get_crypto()
    config = QualysConfig(
        username="quays2user1",
        encrypted_password=crypto.encrypt("secret"),
        connector_uuid="test-connector-uuid",
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


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


def _make_source_result(records=None, fetched=None) -> SourceFetchResult:
    if records is None:
        records = [{"hostname": "asset-1"}, {"hostname": "asset-2"}]
    return SourceFetchResult(
        records=records,
        records_fetched=fetched if fetched is not None else len(records),
        pages_fetched=1,
        partial=False,
    )


def _make_submit_result(count=2, failures=None) -> QualysSubmitResult:
    return QualysSubmitResult(
        submitted_count=count,
        failed_count=len(failures) if failures else 0,
        failures=failures or [],
    )


@pytest.mark.asyncio
async def test_all_endpoints_succeed_status_success(db_session):
    """All endpoints succeed → RunHistory.status=success, all EndpointRunLog rows status=success."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep1 = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    ep2 = _seed_endpoint(db_session, connector.id, path="/servers", display_order=1)
    _seed_mapping(db_session, ep1.id)
    _seed_mapping(db_session, ep2.id)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=_make_source_result()),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=2)),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated_run = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.success

    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).order_by(EndpointRunLog.execution_order).all()
    assert len(logs) == 2
    assert all(log.status == "success" for log in logs)


@pytest.mark.asyncio
async def test_first_endpoint_fails_partial_success(db_session):
    """First endpoint fetch raises Exception → partial_success, first log failed, second log success."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep1 = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    ep2 = _seed_endpoint(db_session, connector.id, path="/servers", display_order=1)
    _seed_mapping(db_session, ep2.id)
    run = _seed_run(db_session, connector.id)

    call_count = 0

    async def fetch_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Source fetch failed for endpoint 1")
        return _make_source_result()

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(side_effect=fetch_side_effect),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=2)),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated_run = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.partial_success

    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).order_by(EndpointRunLog.execution_order).all()
    assert len(logs) == 2
    assert logs[0].status == "failed"
    assert logs[0].error_message is not None
    assert "Source fetch failed for endpoint 1" in logs[0].error_message
    assert logs[1].status == "success"


@pytest.mark.asyncio
async def test_all_endpoints_fail_status_failed(db_session):
    """All endpoints fail → RunHistory.status=failed."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep1 = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    ep2 = _seed_endpoint(db_session, connector.id, path="/servers", display_order=1)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(side_effect=RuntimeError("fetch failed")),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result()),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated_run = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.failed

    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 2
    assert all(log.status == "failed" for log in logs)


@pytest.mark.asyncio
async def test_zero_records_endpoint_is_success(db_session):
    """Zero-records endpoint → RunHistory.status=success."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=SourceFetchResult(records=[], records_fetched=0, pages_fetched=1, partial=False)),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=0)),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated_run = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.success
    assert updated_run.records_fetched == 0

    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 1
    assert logs[0].status == "success"
    assert logs[0].records_fetched == 0


@pytest.mark.asyncio
async def test_aggregate_totals_equal_sum_of_endpoint_logs(db_session):
    """RunHistory.records_fetched == sum of EndpointRunLog.records_fetched."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep1 = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    ep2 = _seed_endpoint(db_session, connector.id, path="/servers", display_order=1)
    _seed_mapping(db_session, ep1.id)
    _seed_mapping(db_session, ep2.id)
    run = _seed_run(db_session, connector.id)

    # Endpoint 1 returns 3 records, endpoint 2 returns 5 records
    results = [
        SourceFetchResult(
            records=[{"hostname": f"a-{i}"} for i in range(3)],
            records_fetched=3,
            pages_fetched=1,
            partial=False,
        ),
        SourceFetchResult(
            records=[{"hostname": f"b-{i}"} for i in range(5)],
            records_fetched=5,
            pages_fetched=1,
            partial=False,
        ),
    ]

    call_count = 0

    async def fetch_side_effect(*args, **kwargs):
        nonlocal call_count
        result = results[call_count]
        call_count += 1
        return result

    async def submit_side_effect(batch, *args, **kwargs):
        return QualysSubmitResult(submitted_count=len(batch), failed_count=0, failures=[])

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(side_effect=fetch_side_effect),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(side_effect=submit_side_effect),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated_run = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()

    assert updated_run.records_fetched == sum(log.records_fetched for log in logs)
    assert updated_run.records_fetched == 8


@pytest.mark.asyncio
async def test_execution_order_matches_loop_index(db_session):
    """EndpointRunLog.execution_order == loop index (0, 1, 2...)."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep1 = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    ep2 = _seed_endpoint(db_session, connector.id, path="/servers", display_order=1)
    ep3 = _seed_endpoint(db_session, connector.id, path="/devices", display_order=2)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=_make_source_result(records=[])),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=0)),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).order_by(EndpointRunLog.execution_order).all()
    assert len(logs) == 3
    assert [log.execution_order for log in logs] == [0, 1, 2]


@pytest.mark.asyncio
async def test_disabled_endpoint_produces_no_log(db_session):
    """Disabled endpoint produces no EndpointRunLog row."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep_enabled = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0, is_enabled=True)
    ep_disabled = _seed_endpoint(db_session, connector.id, path="/servers", display_order=1, is_enabled=False)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=_make_source_result(records=[])),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=0)),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 1
    assert logs[0].endpoint_id == ep_enabled.id


@pytest.mark.asyncio
async def test_fetch_all_pages_called_once_per_enabled_endpoint(db_session):
    """fetch_all_pages is called once per enabled endpoint."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep1 = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    ep2 = _seed_endpoint(db_session, connector.id, path="/servers", display_order=1)
    ep3 = _seed_endpoint(db_session, connector.id, path="/devices", display_order=2)
    run = _seed_run(db_session, connector.id)

    mock_fetch = AsyncMock(return_value=_make_source_result(records=[]))

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=mock_fetch,
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=0)),
    ):
        await run_ingestion(run.id)

    assert mock_fetch.call_count == 3


# --------------- Per-endpoint QualysAdapterError isolation Tests ---------------


@pytest.mark.asyncio
async def test_qualys_submit_failure_captured_with_http_exchange(db_session):
    """QualysAdapterError with http dicts → EndpointRunLog has http_request/http_response populated."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    _seed_mapping(db_session, ep.id)
    run = _seed_run(db_session, connector.id)

    error_context = {
        "http_request": {
            "method": "POST",
            "url": "https://qualys.example.com/rest/2.0/am/connector/asset/data/sync",
            "headers": {"authorization": "[REDACTED]", "content-type": "application/json"},
        },
        "http_response": {
            "status_code": 403,
            "body": '{"error": "forbidden"}',
        },
    }

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=_make_source_result()),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(side_effect=QualysAdapterError("forbidden", status_code=403, error_context=error_context)),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.status == "failed"
    assert log.failure_stage == "qualys_submit"
    assert log.http_request is not None
    assert log.http_request["method"] == "POST"
    assert log.http_request["headers"]["authorization"] == "[REDACTED]"
    assert log.http_response is not None
    assert log.http_response["status_code"] == 403


@pytest.mark.asyncio
async def test_qualys_submit_connection_error_no_capture(db_session):
    """QualysAdapterError with no http dicts (connection error) → http_request/http_response are None."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    _seed_mapping(db_session, ep.id)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=_make_source_result()),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(side_effect=QualysAdapterError("timeout", error_type="qualys_timeout")),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.status == "failed"
    assert log.http_request is None
    assert log.http_response is None


@pytest.mark.asyncio
async def test_qualys_capture_uses_body_override_with_record_count(db_session):
    """Captured Qualys request body uses body_preview from package error context."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    _seed_mapping(db_session, ep.id)
    run = _seed_run(db_session, connector.id)

    error_context = {
        "http_request": {
            "method": "POST",
            "url": "https://qualys.example.com/rest/2.0/am/connector/asset/data/sync",
            "headers": {"authorization": "[REDACTED]"},
            "body_preview": '{"assets": [2 asset records omitted]}',
        },
        "http_response": {
            "status_code": 500,
            "body": '{"error": "server error"}',
        },
    }

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=_make_source_result()),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(side_effect=QualysAdapterError("server error", status_code=500, error_context=error_context)),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.http_request is not None
    # Body preview comes from package error context
    assert "asset records omitted" in log.http_request["body_preview"]


@pytest.mark.asyncio
async def test_qualys_submit_failure_remaining_endpoints_continue(db_session):
    """When one endpoint fails Qualys submit, remaining endpoints still execute → partial_success."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep1 = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    ep2 = _seed_endpoint(db_session, connector.id, path="/servers", display_order=1)
    _seed_mapping(db_session, ep1.id)
    _seed_mapping(db_session, ep2.id)
    run = _seed_run(db_session, connector.id)

    call_count = 0
    error_context = {
        "http_request": {
            "method": "POST",
            "url": "https://qualys.example.com/api",
            "headers": {"authorization": "[REDACTED]"},
        },
        "http_response": {
            "status_code": 403,
            "body": '{"error": "forbidden"}',
        },
    }

    async def submit_side_effect(batch, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise QualysAdapterError("forbidden", status_code=403, error_context=error_context)
        return _make_submit_result(count=len(batch))

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=_make_source_result()),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(side_effect=submit_side_effect),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated_run = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.partial_success

    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).order_by(EndpointRunLog.execution_order).all()
    assert len(logs) == 2
    assert logs[0].status == "failed"
    assert logs[1].status == "success"


@pytest.mark.asyncio
async def test_preflight_validation_fails_run_before_endpoint_loop(db_session):
    """Pre-flight validation (missing credentials) fails entire run before any endpoint executes."""
    connector = _seed_connector(db_session)
    # Create config with NO credentials (no password)
    config = QualysConfig(
        username="quays2user1",
        encrypted_password=None,
        connector_uuid="test-connector-uuid",
    )
    db_session.add(config)
    db_session.commit()

    ep = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    _seed_mapping(db_session, ep.id)
    run = _seed_run(db_session, connector.id)

    mock_fetch = AsyncMock(return_value=_make_source_result())

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=mock_fetch,
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result()),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated_run = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.failed
    assert "credentials" in (updated_run.error_message or "").lower()

    # No endpoint logs should exist -- run failed before endpoint loop
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 0

    # fetch_all_pages should NOT have been called
    assert mock_fetch.call_count == 0


# --------------- Pipeline Stage Tracking Tests ---------------


@pytest.mark.asyncio
async def test_source_fetch_failure_sets_stage(db_session):
    """Source fetch exception (source_result is None) sets failure_stage='source_fetch'."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(side_effect=RuntimeError("connection refused")),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result()),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 1
    assert logs[0].status == "failed"
    assert logs[0].failure_stage == "source_fetch"
    # HTTP payloads should be None since source_result was never assigned
    assert logs[0].http_request is None
    assert logs[0].http_response is None


@pytest.mark.asyncio
async def test_transformation_failure_sets_stage(db_session):
    """Transformation exception (source_result exists) sets failure_stage='transformation'."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    _seed_mapping(db_session, ep.id)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=_make_source_result()),
    ), patch(
        "app.services.ingestion_service.apply_mappings",
        side_effect=ValueError("bad mapping rule"),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result()),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 1
    assert logs[0].status == "failed"
    assert logs[0].failure_stage == "transformation"


@pytest.mark.asyncio
async def test_successful_run_has_no_failure_stage(db_session):
    """Successful endpoint run has failure_stage=None."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    _seed_mapping(db_session, ep.id)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=_make_source_result()),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=2)),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 1
    assert logs[0].status == "success"
    assert logs[0].failure_stage is None


# --------------- Canvas Execution Path Tests ---------------


def _seed_canvas(db, connector_id: str, name: str = "Test Canvas", is_enabled: bool = True) -> Canvas:
    canvas = Canvas(
        connector_id=connector_id,
        name=name,
        is_enabled=is_enabled,
    )
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


def _seed_canvas_endpoint(
    db,
    canvas_id: str,
    endpoint_id: str,
    parent_ref_id: str | None = None,
    tree_order: int = 0,
    max_concurrency: int = 5,
) -> CanvasEndpoint:
    ce = CanvasEndpoint(
        canvas_id=canvas_id,
        endpoint_id=endpoint_id,
        parent_ref_id=parent_ref_id,
        tree_order=tree_order,
        max_concurrency=max_concurrency,
    )
    db.add(ce)
    db.commit()
    db.refresh(ce)
    return ce


@pytest.mark.asyncio
async def test_run_ingestion_no_canvases_uses_legacy_path(db_session):
    """Connector with no canvases executes all endpoints via legacy _run_endpoint path."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep1 = _seed_endpoint(db_session, connector.id, path="/assets", display_order=0)
    ep2 = _seed_endpoint(db_session, connector.id, path="/servers", display_order=1)
    _seed_mapping(db_session, ep1.id)
    _seed_mapping(db_session, ep2.id)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=_make_source_result()),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=2)),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated_run = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.success

    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).all()
    assert len(logs) == 2
    # No canvas_id should be set -- these went through orphan/legacy path
    assert all(log.canvas_id is None for log in logs)


@pytest.mark.asyncio
async def test_run_canvas_creates_root_log_with_records_fetched(db_session):
    """Canvas with single root endpoint creates EndpointRunLog with records_fetched, records_submitted=0."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep = _seed_endpoint(db_session, connector.id, path="/nodes", display_order=0)
    _seed_mapping(db_session, ep.id)
    canvas = _seed_canvas(db_session, connector.id)
    root_ce = _seed_canvas_endpoint(db_session, canvas.id, ep.id, parent_ref_id=None, tree_order=0)
    run = _seed_run(db_session, connector.id)

    source_result = _make_source_result(
        records=[{"node": f"pve{i}"} for i in range(10)],
        fetched=10,
    )

    # Single root with no children -> execute_tree returns merged_records directly
    fan_out_result = FanOutResult(
        merged_records=[{"node": f"pve{i}"} for i in range(10)],
        level_stats=[],
    )

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=source_result),
    ), patch(
        "app.services.ingestion_service.execute_tree",
        new=AsyncMock(return_value=fan_out_result),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=10)),
    ):
        import httpx
        async with httpx.AsyncClient() as client:
            logs = await _run_canvas(db_session, run, connector, canvas, None, client, 0)

    assert len(logs) >= 1
    root_log = logs[0]
    assert root_log.records_fetched == 10
    assert root_log.records_submitted == 0  # D-14: root is data source only
    assert root_log.canvas_id == canvas.id
    assert root_log.status == "success"


@pytest.mark.asyncio
async def test_run_canvas_creates_child_log_from_level_stats(db_session):
    """Canvas with root + child: child EndpointRunLog has child_requests_* from LevelStats."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    root_ep = _seed_endpoint(db_session, connector.id, path="/nodes", display_order=0)
    child_ep = _seed_endpoint(db_session, connector.id, path="/nodes/{node}/vms", display_order=1)
    _seed_mapping(db_session, child_ep.id)
    canvas = _seed_canvas(db_session, connector.id)
    root_ce = _seed_canvas_endpoint(db_session, canvas.id, root_ep.id, parent_ref_id=None, tree_order=0)
    child_ce = _seed_canvas_endpoint(db_session, canvas.id, child_ep.id, parent_ref_id=root_ce.id, tree_order=1)
    run = _seed_run(db_session, connector.id)

    source_result = _make_source_result(
        records=[{"node": "pve1"}, {"node": "pve2"}],
        fetched=2,
    )

    fan_out_result = FanOutResult(
        merged_records=[{"vmid": 100, "_parent.node": "pve1"}, {"vmid": 200, "_parent.node": "pve2"}],
        level_stats=[
            LevelStats(
                endpoint_id=child_ce.id,  # canvas_endpoint.id, not connector_endpoint.id
                children_attempted=5,
                children_succeeded=4,
                children_failed=1,
                children_skipped=0,
            ),
        ],
    )

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=source_result),
    ), patch(
        "app.services.ingestion_service.execute_tree",
        new=AsyncMock(return_value=fan_out_result),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=2)),
    ):
        import httpx
        async with httpx.AsyncClient() as client:
            logs = await _run_canvas(db_session, run, connector, canvas, None, client, 0)

    # Root log + child log
    assert len(logs) >= 2
    child_log = [l for l in logs if l.endpoint_id == child_ep.id][0]
    assert child_log.child_requests_total == 5
    assert child_log.child_requests_failed == 1
    assert child_log.child_requests_skipped == 0
    assert child_log.canvas_id == canvas.id
    assert child_log.status == "partial_success"  # has failures


@pytest.mark.asyncio
async def test_orphan_detection_excludes_canvas_endpoints(db_session):
    """Endpoints referenced in a canvas are excluded from orphan path; only unreferenced run via legacy."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep1 = _seed_endpoint(db_session, connector.id, path="/nodes", display_order=0)
    ep2 = _seed_endpoint(db_session, connector.id, path="/nodes/{node}/vms", display_order=1)
    ep3 = _seed_endpoint(db_session, connector.id, path="/standalone", display_order=2)
    _seed_mapping(db_session, ep1.id)
    _seed_mapping(db_session, ep2.id)
    _seed_mapping(db_session, ep3.id)

    canvas = _seed_canvas(db_session, connector.id)
    root_ce = _seed_canvas_endpoint(db_session, canvas.id, ep1.id, parent_ref_id=None, tree_order=0)
    child_ce = _seed_canvas_endpoint(db_session, canvas.id, ep2.id, parent_ref_id=root_ce.id, tree_order=1)
    # ep3 is NOT in the canvas -- it's an orphan

    run = _seed_run(db_session, connector.id)

    source_result = _make_source_result(records=[{"node": "pve1"}], fetched=1)
    fan_out_result = FanOutResult(
        merged_records=[{"vmid": 100, "_parent.node": "pve1"}],
        level_stats=[
            LevelStats(
                endpoint_id=child_ce.id,
                children_attempted=1,
                children_succeeded=1,
            ),
        ],
    )

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=source_result),
    ), patch(
        "app.services.ingestion_service.execute_tree",
        new=AsyncMock(return_value=fan_out_result),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(return_value=_make_submit_result(count=1)),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    logs = db_session.query(EndpointRunLog).filter(EndpointRunLog.run_id == run.id).order_by(EndpointRunLog.execution_order).all()

    # Canvas logs (root + child) + orphan log (ep3) = 3
    assert len(logs) == 3

    # Canvas logs have canvas_id set
    canvas_logs = [l for l in logs if l.canvas_id is not None]
    assert len(canvas_logs) == 2

    # Orphan log (ep3) has no canvas_id
    orphan_logs = [l for l in logs if l.canvas_id is None]
    assert len(orphan_logs) == 1
    assert orphan_logs[0].endpoint_id == ep3.id


@pytest.mark.asyncio
async def test_run_canvas_root_fetch_failure(db_session):
    """Root endpoint fetch failure creates EndpointRunLog with status=failed, failure_stage=source_fetch."""
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    ep = _seed_endpoint(db_session, connector.id, path="/nodes", display_order=0)
    canvas = _seed_canvas(db_session, connector.id)
    root_ce = _seed_canvas_endpoint(db_session, canvas.id, ep.id, parent_ref_id=None, tree_order=0)
    run = _seed_run(db_session, connector.id)

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(side_effect=RuntimeError("connection refused")),
    ):
        import httpx
        async with httpx.AsyncClient() as client:
            logs = await _run_canvas(db_session, run, connector, canvas, None, client, 0)

    assert len(logs) == 1
    log = logs[0]
    assert log.status == "failed"
    assert log.failure_stage == "source_fetch"
    assert log.canvas_id == canvas.id
    assert log.records_fetched == 0
    assert "connection refused" in log.error_message


# --------------- Phase 54 Wiring Smoke Tests ---------------


class TestCanvasSyncWiring:
    """Verify data_root and pagination_strategies propagation in _run_canvas."""

    def test_resolve_pagination_config_imported_in_ingestion(self):
        """Confirm ingestion_service can access resolve_pagination_config."""
        from app.services.ingestion_service import resolve_pagination_config as rpc
        assert callable(rpc)

    def test_resolve_pagination_config_imported_in_fan_out(self):
        """Confirm fan_out_executor can access resolve_pagination_config."""
        from app.services.fan_out_executor import resolve_pagination_config as rpc
        assert callable(rpc)

    def test_endpoint_run_log_has_canvas_endpoint_id(self):
        """Confirm EndpointRunLog model has canvas_endpoint_id attribute."""
        from app.models.run_history import EndpointRunLog
        assert hasattr(EndpointRunLog, 'canvas_endpoint_id')

    def test_level_stats_has_records_fetched(self):
        """Confirm LevelStats dataclass has records_fetched field."""
        from app.services.fan_out_executor import LevelStats
        stats = LevelStats(endpoint_id="test")
        assert hasattr(stats, 'records_fetched')
        assert stats.records_fetched == 0
