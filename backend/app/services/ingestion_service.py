from __future__ import annotations

import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)
from pydantic import TypeAdapter

from app.db.session import SessionLocal
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping
from app.models.qualys_config import QualysConfig
from app.models.run_history import EndpointRunLog, RunFailure, RunHistory, RunStatus
from app.schemas.field_mapping import FieldMappingRule
from app.services.fan_out_executor import execute_tree, FanOutResult, _build_tree
from app.services.path_resolver import resolve_path
from app.services.source_client import SourceFetchResult, fetch_all_pages, resolve_pagination_config
from app.services.transform_engine import apply_mappings
from app.services.qualys_adapter import QualysAdapterError, QualysFailure, submit_batch, _decrypt_secret
from app.services.connector_service import HTTPX_TIMEOUT
from app.services.payload_capture import cleanup_old_payloads
from app.services.exclusion_filter import apply_exclusion_rules
from app.services.event_collector import (
    EventCollector, STAGE_FETCH, STAGE_TRANSFORM, STAGE_EXCLUSION, STAGE_QUALYS,
    API_CALL, TRANSFORM_DECISION, EXCLUSION_RESULT, QUALYS_BATCH, QUALYS_REJECTION,
)
from app.schemas.exclusion_rule import ExclusionRule

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
        if mapping.mapping_type == "conditional" and mapping.conditions:
            payload["conditional_config"] = {
                "conditions": mapping.conditions,
                "fallback": mapping.fallback,
            }
        if mapping.mapping_type == "collect":
            payload["array_path"] = mapping.array_path
            payload["extract_field"] = mapping.extract_field
            payload["collect_filter"] = mapping.collect_filter
            payload["separator"] = mapping.separator
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
    collector: EventCollector | None = None,
) -> EndpointRunLog:
    records_fetched = 0
    records_submitted = 0
    records_failed = 0
    current_batch_size = 0
    source_result: SourceFetchResult | None = None

    try:
        resolved_url = connector.base_url.rstrip("/") + "/" + endpoint.path.lstrip("/")
        logger.debug(
            "Endpoint %s: fetching from %s", endpoint.path, resolved_url,
        )

        # --- Source fetch stage ---
        if collector:
            collector.start_stage(STAGE_FETCH)

        source_result = await fetch_all_pages(
            connector, url=resolved_url, client=client,
            data_root=endpoint.data_root,
            pagination_strategies=resolve_pagination_config(endpoint.pagination_config),
        )
        records_fetched = source_result.records_fetched

        if collector:
            collector.end_stage(STAGE_FETCH, records_in=0, records_out=records_fetched)
            collector.add_detail(API_CALL, STAGE_FETCH,
                f"GET {resolved_url} -> {records_fetched} records",
                {"url": resolved_url, "records": records_fetched,
                 "http_request": source_result.http_request,
                 "http_response": source_result.http_response})

        logger.debug(
            "Endpoint %s: fetched %d records (partial=%s)",
            endpoint.path, records_fetched, source_result.partial,
        )

        # --- Transform stage ---
        if collector:
            collector.start_stage(STAGE_TRANSFORM)

        mappings = (
            db.query(FieldMapping)
            .filter(FieldMapping.endpoint_id == endpoint.id)
            .order_by(FieldMapping.created_at.asc())
            .all()
        )
        mapping_rules = _build_mapping_rules(mappings)
        transformed_records = [apply_mappings(record, mapping_rules) for record in source_result.records]

        if collector:
            collector.end_stage(STAGE_TRANSFORM, records_in=records_fetched, records_out=len(transformed_records))

        # --- Qualys submit stage ---
        if collector:
            collector.start_stage(STAGE_QUALYS)

        failures: list[QualysFailure] = []
        batches = _chunk_records(transformed_records, QUALYS_BATCH_SIZE)
        logger.debug(
            "Endpoint %s: submitting %d records in %d batches",
            endpoint.path, len(transformed_records), len(batches),
        )
        for batch_idx, batch in enumerate(batches):
            if not batch:
                continue
            current_batch_size = len(batch)
            result = await submit_batch(batch, connector, qualys_config)
            records_submitted += result.submitted_count
            failures.extend(result.failures)
            if collector:
                collector.add_detail(QUALYS_BATCH, STAGE_QUALYS,
                    f"Batch {batch_idx+1}/{len(batches)}: {result.submitted_count} accepted, {len(result.failures)} rejected",
                    {"batch": batch_idx+1, "total_batches": len(batches),
                     "accepted": result.submitted_count, "rejected": len(result.failures)})

        records_failed = len(failures)

        if collector:
            status = "success" if records_failed == 0 else "partial_success"
            collector.end_stage(STAGE_QUALYS, records_in=len(transformed_records), records_out=records_submitted, status=status)

            # Group failures by error_message for rejection detail (per D-07)
            if failures:
                reason_groups: dict[str, list[str]] = {}
                for f in failures:
                    reason_groups.setdefault(f.error_message, []).append(f.record_identifier)
                for reason, record_ids in reason_groups.items():
                    collector.add_detail(QUALYS_REJECTION, STAGE_QUALYS,
                        f"{len(record_ids)} records: {reason}",
                        {"reason": reason, "count": len(record_ids), "record_ids": record_ids})

        log = EndpointRunLog(
            run_id=run.id,
            endpoint_id=endpoint.id,
            execution_order=idx,
            records_fetched=records_fetched,
            records_submitted=records_submitted,
            records_failed=records_failed,
            status="success",
            error_message=None,
            http_request=source_result.http_request,
            http_response=source_result.http_response,
        )
        db.add(log)
        db.commit()
        return log

    except QualysAdapterError as exc:
        if collector:
            collector.end_stage(STAGE_QUALYS, records_in=len(transformed_records) if source_result else 0, records_out=records_submitted, status="failed", error=str(exc))
        http_req = exc.error_context.get("http_request")
        http_resp = exc.error_context.get("http_response")
        log = EndpointRunLog(
            run_id=run.id,
            endpoint_id=endpoint.id,
            execution_order=idx,
            records_fetched=records_fetched,
            records_submitted=records_submitted,
            records_failed=records_failed,
            status="failed",
            error_message=str(exc),
            failure_stage="qualys_submit",
            http_request=http_req,
            http_response=http_resp,
        )
        db.add(log)
        db.commit()
        return log

    except Exception as exc:
        failure_stage = "source_fetch" if source_result is None else "transformation"
        if collector:
            collector.end_stage(STAGE_FETCH if source_result is None else STAGE_TRANSFORM, records_in=0, records_out=0, status="failed", error=str(exc))
        log = EndpointRunLog(
            run_id=run.id,
            endpoint_id=endpoint.id,
            execution_order=idx,
            records_fetched=records_fetched,
            records_submitted=records_submitted,
            records_failed=records_failed,
            status="failed",
            error_message=str(exc),
            failure_stage=failure_stage,
            http_request=source_result.http_request if source_result else None,
            http_response=source_result.http_response if source_result else None,
        )
        db.add(log)
        db.commit()
        return log


async def _run_canvas(
    db,
    run: RunHistory,
    connector: Connector,
    canvas: Canvas,
    qualys_config,
    client: httpx.AsyncClient,
    execution_offset: int,
    collector: EventCollector | None = None,
) -> list[EndpointRunLog]:
    """Execute a canvas endpoint tree and create EndpointRunLogs.

    Per D-01/D-03: executes tree via fan_out_executor, writes one
    EndpointRunLog per canvas-endpoint. Per D-14: parent endpoints
    skip Qualys submission (data source only).

    Args:
        execution_offset: Starting execution_order for EndpointRunLogs.

    Returns:
        List of EndpointRunLog records created for this canvas.
    """
    logs: list[EndpointRunLog] = []

    # Load canvas endpoints with their connector endpoint paths
    canvas_endpoints = (
        db.query(CanvasEndpoint)
        .filter(CanvasEndpoint.canvas_id == canvas.id)
        .all()
    )
    if not canvas_endpoints:
        return logs

    # Build mapping: canvas_endpoint.id -> CanvasEndpoint (for FK resolution)
    ce_map = {ce.id: ce for ce in canvas_endpoints}

    # Load connector endpoints for path resolution
    endpoint_ids = [ce.endpoint_id for ce in canvas_endpoints]
    connector_endpoints = (
        db.query(ConnectorEndpoint)
        .filter(ConnectorEndpoint.id.in_(endpoint_ids))
        .all()
    )
    ep_map = {ep.id: ep for ep in connector_endpoints}

    # Attach .path, .data_root, .pagination_config to each canvas_endpoint for execute_tree compatibility
    for ce in canvas_endpoints:
        ep = ep_map.get(ce.endpoint_id)
        ce.path = ep.path if ep else ""
        ce.data_root = ep.data_root if ep else None
        ce.pagination_config = ep.pagination_config if ep else None

    # Find root canvas endpoints (parent_ref_id is None)
    roots = [ce for ce in canvas_endpoints if ce.parent_ref_id is None]
    if not roots:
        logger.warning("Canvas %s has no root endpoints", canvas.id)
        return logs

    # Identify leaf endpoints (no children in tree)
    children_map = _build_tree(canvas_endpoints)
    leaf_ids = {ce.id for ce in canvas_endpoints if ce.id not in children_map}

    # Fetch root endpoint records
    root_ce = roots[0]  # Single root per canvas (v1.5 constraint)
    root_ep = ep_map.get(root_ce.endpoint_id)
    if not root_ep:
        logger.error("Canvas %s root endpoint %s not found", canvas.id, root_ce.endpoint_id)
        return logs

    root_url = connector.base_url.rstrip("/") + "/" + root_ep.path.lstrip("/")
    try:
        if collector:
            collector.start_stage(STAGE_FETCH)

        source_result = await fetch_all_pages(
            connector, url=root_url, client=client,
            data_root=root_ep.data_root,
            pagination_strategies=resolve_pagination_config(root_ep.pagination_config),
        )

        if collector:
            collector.end_stage(STAGE_FETCH, records_in=0, records_out=source_result.records_fetched)
            collector.add_detail(API_CALL, STAGE_FETCH,
                f"GET {root_url} -> {source_result.records_fetched} records (root)",
                {"url": root_url, "records": source_result.records_fetched,
                 "http_request": source_result.http_request,
                 "http_response": source_result.http_response})

    except Exception as exc:
        if collector:
            collector.end_stage(STAGE_FETCH, records_in=0, records_out=0, status="failed", error=str(exc))
        # Root fetch failed -- log and return
        log = EndpointRunLog(
            run_id=run.id,
            endpoint_id=root_ep.id,
            canvas_id=canvas.id,
            canvas_endpoint_id=root_ce.id,
            execution_order=execution_offset,
            records_fetched=0,
            records_submitted=0,
            records_failed=0,
            status="failed",
            error_message=str(exc),
            failure_stage="source_fetch",
        )
        db.add(log)
        db.commit()
        return [log]

    if source_result.partial:
        log = EndpointRunLog(
            run_id=run.id,
            endpoint_id=root_ep.id,
            canvas_id=canvas.id,
            canvas_endpoint_id=root_ce.id,
            execution_order=execution_offset,
            records_fetched=0,
            records_submitted=0,
            records_failed=0,
            status="failed",
            error_message="Source API fetch failed after retries",
            failure_stage="source_fetch",
            http_request=source_result.http_request,
            http_response=source_result.http_response,
        )
        db.add(log)
        db.commit()
        return [log]

    # Create root EndpointRunLog (D-14: records_submitted=0, data source only)
    root_log = EndpointRunLog(
        run_id=run.id,
        endpoint_id=root_ep.id,
        canvas_id=canvas.id,
        canvas_endpoint_id=root_ce.id,
        execution_order=execution_offset,
        records_fetched=source_result.records_fetched,
        records_submitted=0,
        records_failed=0,
        status="success",
        http_request=source_result.http_request,
        http_response=source_result.http_response,
    )
    db.add(root_log)
    logs.append(root_log)

    # --- D-03: Filter root records BEFORE fan-out ---
    rule_adapter = TypeAdapter(list[ExclusionRule])
    root_rules_raw = root_ce.exclusion_rules or []
    root_filtered = 0
    if root_rules_raw:
        root_rules = rule_adapter.validate_python(root_rules_raw)
        filtered_root_records, root_filtered = apply_exclusion_rules(
            source_result.records, root_rules
        )
        root_log.records_filtered = root_filtered
        if collector and root_filtered > 0:
            collector.add_detail(EXCLUSION_RESULT, STAGE_EXCLUSION,
                f"Root exclusion: {root_filtered} records excluded",
                {"excluded_count": root_filtered, "remaining": len(filtered_root_records)})
    else:
        filtered_root_records = source_result.records

    # Execute tree (fan-out children)
    fan_out_result = await execute_tree(
        canvas_endpoints=canvas_endpoints,
        root_records=filtered_root_records,
        connector=connector,
        client=client,
    )

    if collector and fan_out_result.level_stats:
        total_child_fetched = sum(s.records_fetched for s in fan_out_result.level_stats)
        collector.add_detail(API_CALL, STAGE_FETCH,
            f"Fan-out: {total_child_fetched} child records from {len(fan_out_result.level_stats)} levels",
            {"child_records": total_child_fetched, "levels": len(fan_out_result.level_stats)})

    # Create EndpointRunLog per child canvas-endpoint from LevelStats
    # PITFALL 1: LevelStats.endpoint_id is canvas_endpoint.id, not connector_endpoint.id
    for idx, stats in enumerate(fan_out_result.level_stats):
        ce = ce_map.get(stats.endpoint_id)
        if not ce:
            continue
        child_log = EndpointRunLog(
            run_id=run.id,
            endpoint_id=ce.endpoint_id,  # FK to connector_endpoints
            canvas_id=canvas.id,
            canvas_endpoint_id=ce.id,
            execution_order=execution_offset + idx + 1,
            records_fetched=stats.records_fetched,
            records_submitted=0,
            records_failed=0,
            child_requests_total=stats.children_attempted,
            child_requests_failed=stats.children_failed,
            child_requests_skipped=stats.children_skipped,
            status="success" if stats.children_failed == 0 else "partial_success",
        )
        db.add(child_log)
        logs.append(child_log)

    # Apply leaf endpoint field mappings to merged records and submit to Qualys (D-04)
    for leaf_ce_id in leaf_ids:
        leaf_ce = ce_map.get(leaf_ce_id)
        if not leaf_ce:
            continue

        # Skip root if it's also a leaf (no children = single endpoint canvas)
        # In that case the root_log already exists and we submit its records directly
        leaf_ep = ep_map.get(leaf_ce.endpoint_id)
        if not leaf_ep:
            continue

        # --- D-10: Apply leaf exclusion rules to merged records ---
        records_before_exclusion = len(fan_out_result.merged_records)
        leaf_rules_raw = leaf_ce.exclusion_rules or []
        leaf_filtered = 0

        if collector:
            collector.start_stage(STAGE_EXCLUSION)

        if leaf_rules_raw:
            leaf_rules = rule_adapter.validate_python(leaf_rules_raw)
            records_to_map, leaf_filtered = apply_exclusion_rules(
                fan_out_result.merged_records, leaf_rules
            )
            # Update the leaf's log with filtered count
            for log in logs:
                if log.canvas_endpoint_id == leaf_ce.id and log != root_log:
                    log.records_filtered = leaf_filtered
                    break
        else:
            records_to_map = fan_out_result.merged_records

        if collector:
            collector.end_stage(STAGE_EXCLUSION, records_in=records_before_exclusion, records_out=len(records_to_map))
            if leaf_filtered > 0:
                collector.add_detail(EXCLUSION_RESULT, STAGE_EXCLUSION,
                    f"Leaf exclusion: {leaf_filtered} records excluded",
                    {"excluded_count": leaf_filtered, "remaining": len(records_to_map)})

        # --- Transform stage ---
        if collector:
            collector.start_stage(STAGE_TRANSFORM)

        mappings = (
            db.query(FieldMapping)
            .filter(FieldMapping.endpoint_id == leaf_ep.id)
            .order_by(FieldMapping.created_at.asc())
            .all()
        )
        mapping_rules = _build_mapping_rules(mappings)
        transformed = [apply_mappings(rec, mapping_rules) for rec in records_to_map]

        if collector:
            collector.end_stage(STAGE_TRANSFORM, records_in=len(records_to_map), records_out=len(transformed))

        # --- Qualys submit stage ---
        if collector:
            collector.start_stage(STAGE_QUALYS)

        # Submit to Qualys in batches
        failures: list[QualysFailure] = []
        batches = _chunk_records(transformed, QUALYS_BATCH_SIZE)
        submitted_count = 0
        try:
            for batch_idx, batch in enumerate(batches):
                if not batch:
                    continue
                result = await submit_batch(batch, connector, qualys_config)
                submitted_count += result.submitted_count
                failures.extend(result.failures)
                if collector:
                    collector.add_detail(QUALYS_BATCH, STAGE_QUALYS,
                        f"Batch {batch_idx+1}/{len(batches)}: {result.submitted_count} accepted, {len(result.failures)} rejected",
                        {"batch": batch_idx+1, "total_batches": len(batches),
                         "accepted": result.submitted_count, "rejected": len(result.failures)})
        except QualysAdapterError as exc:
            if collector:
                collector.end_stage(STAGE_QUALYS, records_in=len(transformed), records_out=submitted_count, status="failed", error=str(exc))
            # Find the leaf's log (it's in the child logs from LevelStats)
            for log in logs:
                if log.canvas_endpoint_id == leaf_ce.id and log != root_log:
                    log.records_submitted = submitted_count
                    log.records_failed = len(failures)
                    log.status = "failed"
                    log.error_message = str(exc)
                    log.failure_stage = "qualys_submit"
                    break
            db.commit()
            continue

        if collector:
            qualys_status = "success" if not failures else "partial_success"
            collector.end_stage(STAGE_QUALYS, records_in=len(transformed), records_out=submitted_count, status=qualys_status)

            # Group failures by error_message for rejection detail (per D-07)
            if failures:
                reason_groups: dict[str, list[str]] = {}
                for f in failures:
                    reason_groups.setdefault(f.error_message, []).append(f.record_identifier)
                for reason, record_ids in reason_groups.items():
                    collector.add_detail(QUALYS_REJECTION, STAGE_QUALYS,
                        f"{len(record_ids)} records: {reason}",
                        {"reason": reason, "count": len(record_ids), "record_ids": record_ids})

        # Update leaf log with submission counts
        for log in logs:
            if log.canvas_endpoint_id == leaf_ce.id and log != root_log:
                log.records_submitted = submitted_count
                log.records_failed = len(failures)
                break

    db.commit()
    return logs


async def run_ingestion(run_id: str, canvas_id: str | None = None) -> None:
    db = SessionLocal()
    run: RunHistory | None = None
    try:
        cleanup_old_payloads(db)  # purge old diagnostic payloads
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

        collector = EventCollector(
            run_id=run.id,
            fault_diagnosis=bool(getattr(connector, 'fault_diagnosis', False)),
        )

        qualys_config = db.query(QualysConfig).first()
        if not qualys_config:
            raise QualysAdapterError(
                "Qualys configuration not found",
                error_type="qualys_not_configured",
            )

        # Pre-flight: validate Qualys credentials can be decrypted
        # This separates "config is broken" (run-level) from "API returned error" (endpoint-level)
        _decrypt_secret(qualys_config)

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

        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT, verify=bool(connector.verify_ssl)) as client:
            # === CANVAS PATH (D-01/D-03): Execute canvas trees first ===
            if canvas_id:
                canvases = (
                    db.query(Canvas)
                    .filter(Canvas.id == canvas_id, Canvas.is_enabled == True)
                    .all()
                )
            else:
                canvases = (
                    db.query(Canvas)
                    .filter(
                        Canvas.connector_id == connector.id,
                        Canvas.is_enabled == True,
                    )
                    .all()
                )

            execution_idx = 0
            for canvas in canvases:
                canvas_logs = await _run_canvas(
                    db, run, connector, canvas, qualys_config, client, execution_idx, collector,
                )
                logs.extend(canvas_logs)
                for cl in canvas_logs:
                    total_fetched += cl.records_fetched
                    total_submitted += cl.records_submitted
                    total_failed += cl.records_failed
                execution_idx += len(canvas_logs)

            # === ORPHAN PATH (D-02): Run endpoints NOT in any enabled canvas ===
            # Only run orphan endpoints if this is a full-connector sync
            if not canvas_id:
                canvas_endpoint_ids = (
                    db.query(CanvasEndpoint.endpoint_id)
                    .join(Canvas, CanvasEndpoint.canvas_id == Canvas.id)
                    .filter(
                        Canvas.connector_id == connector.id,
                        Canvas.is_enabled == True,
                    )
                    .distinct()
                    .all()
                )
                referenced_ids = {row[0] for row in canvas_endpoint_ids}
                orphan_endpoints = [ep for ep in enabled_endpoints if ep.id not in referenced_ids]

                for idx, endpoint in enumerate(orphan_endpoints):
                    log = await _run_endpoint(
                        db, run, connector, endpoint, qualys_config, client, execution_idx + idx, collector,
                    )
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
        collector.flush(db)
        db.commit()

    except QualysAdapterError as exc:
        try:
            collector.flush(db)
        except Exception:
            pass  # Don't let event flush failure mask the original error
        _mark_failed(
            db,
            run,
            exc.error_type,
            str(exc),
            {**exc.error_context, "status_code": exc.status_code},
        )
    except Exception as exc:
        try:
            collector.flush(db)
        except Exception:
            pass  # Don't let event flush failure mask the original error
        _mark_failed(
            db,
            run,
            "ingestion_error",
            str(exc),
            {},
        )
    finally:
        db.close()
