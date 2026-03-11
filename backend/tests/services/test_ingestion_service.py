import os
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.db.base import Base
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping
from app.models.qualys_config import QualysConfig
from app.models.run_history import EndpointRunLog, RunHistory, RunStatus
from app.services.credential_crypto import get_crypto
from app.services.ingestion_service import run_ingestion
from app.services.qualys_client import QualysClientError, QualysFailure, QualysSubmitResult
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
        api_url="https://qualys.example.com",
        username="qualys-user",
        encrypted_password=crypto.encrypt("secret"),
        encrypted_token=None,
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
