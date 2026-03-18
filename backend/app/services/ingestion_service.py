from __future__ import annotations

import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)
from pydantic import TypeAdapter

from app.db.session import SessionLocal
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping
from app.models.qualys_config import QualysConfig
from app.models.run_history import EndpointRunLog, RunFailure, RunHistory, RunStatus
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


def _rollup_status(logs: list[EndpointRunLog]) -> RunStatus:
    if not logs:
        return RunStatus.failed
    statuses = {log.status for log in logs}
    if statuses == {"success"}:
        return RunStatus.success
    if statuses == {"failed"}:
        return RunStatus.failed
    return RunStatus.partial_success


async def _run_endpoint(
    db,
    run: RunHistory,
    connector: Connector,
    endpoint: ConnectorEndpoint,
    qualys_config,
    client: httpx.AsyncClient,
    idx: int,
) -> EndpointRunLog:
    records_fetched = 0
    records_submitted = 0
    records_failed = 0

    try:
        resolved_url = connector.base_url.rstrip("/") + "/" + endpoint.path.lstrip("/")
        logger.debug(
            "Endpoint %s: fetching from %s", endpoint.path, resolved_url,
        )
        source_result = await fetch_all_pages(connector, url=resolved_url, client=client)
        records_fetched = source_result.records_fetched
        logger.debug(
            "Endpoint %s: fetched %d records (partial=%s)",
            endpoint.path, records_fetched, source_result.partial,
        )

        mappings = (
            db.query(FieldMapping)
            .filter(FieldMapping.endpoint_id == endpoint.id)
            .order_by(FieldMapping.created_at.asc())
            .all()
        )
        mapping_rules = _build_mapping_rules(mappings)
        transformed_records = [apply_mappings(record, mapping_rules) for record in source_result.records]

        failures: list[QualysFailure] = []
        batches = _chunk_records(transformed_records, QUALYS_BATCH_SIZE)
        logger.debug(
            "Endpoint %s: submitting %d records in %d batches",
            endpoint.path, len(transformed_records), len(batches),
        )
        for batch in batches:
            if not batch:
                continue
            result = await submit_batch(batch, connector, qualys_config, client=client)
            records_submitted += result.submitted_count
            failures.extend(result.failures)

        records_failed = len(failures)

        log = EndpointRunLog(
            run_id=run.id,
            endpoint_id=endpoint.id,
            execution_order=idx,
            records_fetched=records_fetched,
            records_submitted=records_submitted,
            records_failed=records_failed,
            status="success",
            error_message=None,
        )
        db.add(log)
        db.commit()
        return log

    except QualysClientError:
        # QualysClientError must NOT be caught here — propagate to outer handler
        raise

    except Exception as exc:
        log = EndpointRunLog(
            run_id=run.id,
            endpoint_id=endpoint.id,
            execution_order=idx,
            records_fetched=records_fetched,
            records_submitted=records_submitted,
            records_failed=records_failed,
            status="failed",
            error_message=str(exc),
        )
        db.add(log)
        db.commit()
        return log


async def run_ingestion(run_id: str) -> None:
    db = SessionLocal()
    run: RunHistory | None = None
    try:
        run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
        if not run:
            return

        logger.debug("Starting ingestion run_id=%s connector_id=%s", run_id, run.connector_id)
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

        qualys_config = db.query(QualysConfig).first()
        if not qualys_config:
            raise QualysClientError(
                "Qualys configuration not found",
                error_type="qualys_not_configured",
            )

        enabled_endpoints = (
            db.query(ConnectorEndpoint)
            .filter(
                ConnectorEndpoint.connector_id == connector.id,
                ConnectorEndpoint.is_enabled == True,
            )
            .order_by(ConnectorEndpoint.display_order.asc())
            .all()
        )

        if not enabled_endpoints:
            _mark_failed(
                db,
                run,
                "no_enabled_endpoints",
                "No enabled endpoints configured for this connector",
                {},
            )
            return

        logs: list[EndpointRunLog] = []
        total_fetched = 0
        total_submitted = 0
        total_failed = 0

        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            for idx, endpoint in enumerate(enabled_endpoints):
                log = await _run_endpoint(db, run, connector, endpoint, qualys_config, client, idx)
                logs.append(log)
                total_fetched += log.records_fetched
                total_submitted += log.records_submitted
                total_failed += log.records_failed

        run.records_fetched = total_fetched
        run.records_submitted = total_submitted
        run.records_failed = total_failed
        run.finished_at = datetime.utcnow()
        run.status = _rollup_status(logs)
        logger.debug(
            "Ingestion run_id=%s complete: status=%s fetched=%d submitted=%d failed=%d",
            run_id, run.status.value, total_fetched, total_submitted, total_failed,
        )
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
