import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ingestion_service.db")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.connector import Connector
from app.models.field_mapping import FieldMapping
from app.models.qualys_config import QualysConfig
from app.models.run_history import RunFailure, RunHistory, RunStatus
from app.services.credential_crypto import get_crypto
from app.services.ingestion_service import run_ingestion
from app.services.qualys_client import QualysFailure, QualysSubmitResult
from app.services.source_client import SourceFetchResult


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_connector(db) -> Connector:
    connector = Connector(
        name="Ingestion Connector",
        base_url="https://source.example.com",
        auth_method="bearer_token",
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


def _seed_qualys_config(db) -> None:
    crypto = get_crypto()
    config = QualysConfig(
        api_url="https://qualys.example.com",
        username="qualys-user",
        encrypted_password=crypto.encrypt("secret"),
        encrypted_token=None,
    )
    db.add(config)
    db.commit()


def _seed_mapping(db, connector_id: str) -> None:
    mapping = FieldMapping(
        connector_id=connector_id,
        target_field="name",
        mapping_type="direct_copy",
        source_field="hostname",
    )
    db.add(mapping)
    db.commit()


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


@pytest.mark.asyncio
async def test_run_ingestion_success_updates_counts(db_session):
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    _seed_mapping(db_session, connector.id)
    run = _seed_run(db_session, connector.id)

    source_result = SourceFetchResult(
        records=[{"hostname": "asset-1"}, {"hostname": "asset-2"}],
        records_fetched=2,
        pages_fetched=1,
        partial=False,
    )

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=source_result),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(
            return_value=QualysSubmitResult(
                submitted_count=2,
                failed_count=0,
                failures=[],
            )
        ),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated.status == RunStatus.success
    assert updated.records_fetched == 2
    assert updated.records_submitted == 2
    assert updated.records_failed == 0


@pytest.mark.asyncio
async def test_run_ingestion_marks_partial_on_source_retry_exhaustion(db_session):
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    _seed_mapping(db_session, connector.id)
    run = _seed_run(db_session, connector.id)

    source_result = SourceFetchResult(
        records=[{"hostname": "asset-1"}],
        records_fetched=1,
        pages_fetched=1,
        partial=True,
    )

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=source_result),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(
            return_value=QualysSubmitResult(
                submitted_count=1,
                failed_count=0,
                failures=[],
            )
        ),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated.status == RunStatus.partial_success
    assert updated.error_type == "source_partial"


@pytest.mark.asyncio
async def test_run_ingestion_persists_qualys_failures(db_session):
    connector = _seed_connector(db_session)
    _seed_qualys_config(db_session)
    _seed_mapping(db_session, connector.id)
    run = _seed_run(db_session, connector.id)

    source_result = SourceFetchResult(
        records=[{"hostname": "asset-1"}, {"hostname": "asset-2"}],
        records_fetched=2,
        pages_fetched=1,
        partial=False,
    )
    failures = [
        QualysFailure(record_identifier="asset-1", error_message="missing name"),
        QualysFailure(record_identifier="asset-2", error_message="bad address"),
    ]

    with patch(
        "app.services.ingestion_service.fetch_all_pages",
        new=AsyncMock(return_value=source_result),
    ), patch(
        "app.services.ingestion_service.submit_batch",
        new=AsyncMock(
            return_value=QualysSubmitResult(
                submitted_count=2,
                failed_count=2,
                failures=failures,
            )
        ),
    ):
        await run_ingestion(run.id)

    db_session.expire_all()
    updated = db_session.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated.status == RunStatus.partial_success
    assert updated.records_failed == 2

    failures_rows = db_session.query(RunFailure).filter(RunFailure.run_id == run.id).all()
    assert len(failures_rows) == 2
