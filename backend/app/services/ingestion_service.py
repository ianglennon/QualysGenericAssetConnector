from __future__ import annotations

from datetime import datetime

import httpx
from pydantic import TypeAdapter

from app.db.session import SessionLocal
from app.models.connector import Connector
from app.models.field_mapping import FieldMapping
from app.models.qualys_config import QualysConfig
from app.models.run_history import RunFailure, RunHistory, RunStatus
from app.schemas.field_mapping import FieldMappingRule
from app.services.source_client import SourceFetchResult, fetch_all_pages
from app.services.transform_engine import apply_mappings
from app.services.qualys_client import QualysClientError, QualysFailure, submit_batch
from app.services.connector_service import HTTPX_TIMEOUT

QUALYS_BATCH_SIZE = 100


def create_run(connector_id: str) -> RunHistory:
    db = SessionLocal()
    try:
        run = RunHistory(
            connector_id=connector_id,
            status=RunStatus.running,
            started_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def _chunk_records(records: list[dict], batch_size: int) -> list[list[dict]]:
    if batch_size <= 0:
        return [records]
    return [records[i : i + batch_size] for i in range(0, len(records), batch_size)]


def _build_mapping_rules(mappings: list[FieldMapping]) -> list[FieldMappingRule]:
    adapter = TypeAdapter(FieldMappingRule)
    rules: list[FieldMappingRule] = []
    for mapping in mappings:
        payload = {
            "mapping_type": mapping.mapping_type,
            "target_field": mapping.target_field,
            "source_field": mapping.source_field,
            "static_value": mapping.static_value,
        }
        rules.append(adapter.validate_python(payload))
    return rules


def _mark_failed(
    db,
    run: RunHistory | None,
    error_type: str,
    error_message: str,
    error_context: dict | None,
) -> None:
    if not run:
        return
    run.status = RunStatus.failed
    run.finished_at = datetime.utcnow()
    run.error_type = error_type
    run.error_message = error_message
    run.error_context = error_context or {}
    db.commit()


def _apply_partial_failure_context(run: RunHistory, source_result: SourceFetchResult, failure_count: int) -> None:
    if source_result.partial:
        run.error_type = "source_partial"
        run.error_message = "Source fetch exhausted retries"
        run.error_context = {
            "pages_fetched": source_result.pages_fetched,
            "records_fetched": source_result.records_fetched,
        }
    elif failure_count > 0:
        run.error_type = "qualys_partial"
        run.error_message = "Qualys returned per-record failures"
        run.error_context = {"failed_records": failure_count}


async def run_ingestion(run_id: str) -> None:
    db = SessionLocal()
    run: RunHistory | None = None
    try:
        run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
        if not run:
            return

        connector = db.query(Connector).filter(Connector.id == run.connector_id).first()
        if not connector:
            _mark_failed(
                db,
                run,
                "connector_not_found",
                "Connector not found",
                {"connector_id": run.connector_id},
            )
            return

        mappings = (
            db.query(FieldMapping)
            .filter(FieldMapping.connector_id == connector.id)
            .order_by(FieldMapping.created_at.asc())
            .all()
        )
        mapping_rules = _build_mapping_rules(mappings)

        source_result = await fetch_all_pages(connector)
        transformed_records = [apply_mappings(record, mapping_rules) for record in source_result.records]

        qualys_config = db.query(QualysConfig).first()
        if not qualys_config:
            raise QualysClientError(
                "Qualys configuration not found",
                error_type="qualys_not_configured",
            )

        failures: list[QualysFailure] = []
        submitted_count = 0

        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            for batch in _chunk_records(transformed_records, QUALYS_BATCH_SIZE):
                if not batch:
                    continue
                result = await submit_batch(batch, connector, qualys_config, client=client)
                submitted_count += result.submitted_count
                failures.extend(result.failures)

        for failure in failures:
            db.add(
                RunFailure(
                    run_id=run.id,
                    record_identifier=failure.record_identifier,
                    error_message=failure.error_message,
                )
            )

        run.records_fetched = source_result.records_fetched
        run.records_submitted = submitted_count
        run.records_failed = len(failures)
        run.finished_at = datetime.utcnow()

        if source_result.partial or failures:
            run.status = RunStatus.partial_success
            _apply_partial_failure_context(run, source_result, len(failures))
        else:
            run.status = RunStatus.success
            run.error_type = None
            run.error_message = None
            run.error_context = None

        db.commit()
    except QualysClientError as exc:
        _mark_failed(
            db,
            run,
            exc.error_type,
            str(exc),
            {**exc.error_context, "status_code": exc.status_code},
        )
    except Exception as exc:
        _mark_failed(
            db,
            run,
            "ingestion_error",
            str(exc),
            {},
        )
    finally:
        db.close()
