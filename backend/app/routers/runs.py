from datetime import timedelta
from datetime import datetime as _datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, func, case
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate

from app.core.errors import make_error
from app.core.security import require_role
from app.db.session import get_db
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.run_history import RunHistory, RunFailure, RunStatus, EndpointRunLog
from app.models.run_event import RunEvent
from app.schemas.run_history import RunHistoryResponse, RunFailureSummary, EndpointRunLogResponse, RunStatsResponse
from app.schemas.run_event import StageEntry, EventEntry, RunEventsResponse
from app.services.ingestion_service import create_run, run_ingestion
from app.services.validation import validate_endpoint_mappings

router = APIRouter(tags=["runs"])


def _map_failures(failures: list[RunFailure]) -> list[RunFailureSummary]:
    return [
        RunFailureSummary(
            record_identifier=failure.record_identifier,
            error_message=failure.error_message,
            created_at=failure.created_at,
        )
        for failure in failures
    ]


def _to_response(
    run: RunHistory,
    failures: list[RunFailure],
    endpoint_logs: list[EndpointRunLog] | None = None,
    endpoint_lookup: dict[str, ConnectorEndpoint] | None = None,
    include_payloads: bool = False,
    canvas_lookup: dict[str, str] | None = None,
) -> RunHistoryResponse:
    ep_lookup = endpoint_lookup or {}
    c_lookup = canvas_lookup or {}

    def _map_endpoint_log(log: EndpointRunLog) -> EndpointRunLogResponse:
        ep = ep_lookup.get(log.endpoint_id)
        return EndpointRunLogResponse(
            id=log.id,
            run_id=log.run_id,
            endpoint_id=log.endpoint_id,
            endpoint_name=ep.name if ep else None,
            endpoint_path=ep.path if ep else None,
            execution_order=log.execution_order,
            records_fetched=log.records_fetched,
            records_submitted=log.records_submitted,
            records_failed=log.records_failed,
            status=log.status,
            error_message=log.error_message,
            failure_stage=log.failure_stage,
            http_request=log.http_request if include_payloads else None,
            http_response=log.http_response if include_payloads else None,
            created_at=log.created_at,
            canvas_id=log.canvas_id,
            canvas_name=c_lookup.get(log.canvas_id) if log.canvas_id else None,
            child_requests_total=log.child_requests_total,
            child_requests_failed=log.child_requests_failed,
            child_requests_skipped=log.child_requests_skipped,
            depth=getattr(log, 'depth', None),
            endpoint_role=getattr(log, 'endpoint_role', None),
        )

    return RunHistoryResponse(
        id=run.id,
        connector_id=run.connector_id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        started_at=run.started_at,
        finished_at=run.finished_at,
        records_fetched=run.records_fetched,
        records_submitted=run.records_submitted,
        records_failed=run.records_failed,
        base_records_total=getattr(run, 'base_records_total', None),
        base_records_enriched=getattr(run, 'base_records_enriched', None),
        base_records_submitted=getattr(run, 'base_records_submitted', None),
        base_records_failed=getattr(run, 'base_records_failed', None),
        base_records_full=getattr(run, 'base_records_full', None),
        base_records_partial=getattr(run, 'base_records_partial', None),
        base_records_base_only=getattr(run, 'base_records_base_only', None),
        error_type=run.error_type,
        error_message=run.error_message,
        error_context=run.error_context,
        failures=_map_failures(failures),
        endpoint_logs=[_map_endpoint_log(log) for log in (endpoint_logs or [])],
    )


def _fetch_failures_by_run(db: Session, run_ids: list[str]) -> dict[str, list[RunFailure]]:
    if not run_ids:
        return {}
    failures = (
        db.query(RunFailure)
        .filter(RunFailure.run_id.in_(run_ids))
        .order_by(RunFailure.created_at.asc())
        .all()
    )
    grouped: dict[str, list[RunFailure]] = {run_id: [] for run_id in run_ids}
    for failure in failures:
        grouped.setdefault(failure.run_id, []).append(failure)
    return grouped


@router.get("/runs", response_model=Page[RunHistoryResponse])
def list_runs(
    db: Session = Depends(get_db),
    params: Params = Depends(),
    _user=Depends(require_role("admin", "operator")),
    connector_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """List all runs across all connectors with cursor pagination."""
    # Build query returning only RunHistory objects (paginator validates against response_model)
    query = (
        select(RunHistory)
        .order_by(desc(RunHistory.started_at))
    )

    # Apply optional filters
    if connector_id is not None:
        query = query.where(RunHistory.connector_id == connector_id)

    if status is not None:
        try:
            query = query.where(RunHistory.status == RunStatus(status))
        except ValueError:
            pass  # Silently ignore unknown status values

    if date_from is not None:
        try:
            dt_from = _datetime.strptime(date_from, "%Y-%m-%d")
            query = query.where(RunHistory.started_at >= dt_from)
        except ValueError:
            pass  # Silently ignore malformed dates

    if date_to is not None:
        try:
            dt_to = _datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            query = query.where(RunHistory.started_at <= dt_to)
        except ValueError:
            pass  # Silently ignore malformed dates

    # Paginate
    page = paginate(db, query, params)

    # Batch-load connector names for this page
    connector_ids = list({run.connector_id for run in page.items})
    connectors = (
        db.query(Connector)
        .filter(Connector.id.in_(connector_ids))
        .all()
    ) if connector_ids else []
    connector_name_map = {c.id: c.name for c in connectors}

    # Transform results to include connector_name and failures
    items = []
    for run in page.items:
        # Load failures if status is failed or partial_success
        failures = []
        if run.status in ["failed", "partial_success"]:
            failures_query = db.query(RunFailure).filter_by(run_id=run.id).limit(10).all()
            failures = failures_query

        response = _to_response(run, failures)
        response.connector_name = connector_name_map.get(run.connector_id)
        items.append(response)

    page.items = items
    return page


@router.get("/runs/stats", response_model=RunStatsResponse)
def get_runs_stats(
    db: Session = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
):
    """Return aggregate run statistics for dashboard cards."""
    now = _datetime.utcnow()
    cutoff_24h = now - timedelta(hours=24)

    total_runs = db.query(func.count(RunHistory.id)).scalar() or 0

    if total_runs == 0:
        return RunStatsResponse(
            total_runs=0,
            success_rate=0.0,
            last_sync_at=None,
            recent_runs_24h=0,
        )

    # Count runs with status in success or partial_success
    successful_count = (
        db.query(func.count(RunHistory.id))
        .filter(RunHistory.status.in_([RunStatus.success, RunStatus.partial_success]))
        .scalar()
        or 0
    )

    success_rate = float(successful_count) / float(total_runs)

    last_sync_at = db.query(func.max(RunHistory.finished_at)).scalar()

    recent_runs_24h = (
        db.query(func.count(RunHistory.id))
        .filter(RunHistory.started_at >= cutoff_24h)
        .scalar()
        or 0
    )

    return RunStatsResponse(
        total_runs=total_runs,
        success_rate=success_rate,
        last_sync_at=last_sync_at,
        recent_runs_24h=recent_runs_24h,
    )


@router.get("/runs/{run_id}/events", response_model=RunEventsResponse)
def get_run_events(
    run_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
    limit: int = Query(200, ge=1, le=1000),
):
    """Return pipeline event timeline for a run (stage summaries + detail events)."""
    run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=404,
            detail=make_error("RUN_NOT_FOUND", "Run not found", {"run_id": run_id}),
        )

    all_events = (
        db.query(RunEvent)
        .filter(RunEvent.run_id == run_id)
        .order_by(RunEvent.timestamp.asc())
        .all()
    )

    # Separate stage summaries from detail events
    stages: list[StageEntry] = []
    detail_events: list[RunEvent] = []
    for ev in all_events:
        if ev.event_type == "stage_summary":
            d = ev.detail or {}
            stages.append(
                StageEntry(
                    stage=ev.stage,
                    records_in=d.get("records_in", 0),
                    records_out=d.get("records_out", 0),
                    duration_ms=d.get("duration_ms", 0),
                    status=d.get("status", "unknown"),
                    error=d.get("error"),
                )
            )
        else:
            detail_events.append(ev)

    total_events = len(detail_events)
    limited_events = detail_events[:limit]

    events = [
        EventEntry(
            id=ev.id,
            timestamp=ev.timestamp,
            event_type=ev.event_type,
            stage=ev.stage,
            message=ev.message,
            detail=ev.detail,
        )
        for ev in limited_events
    ]

    return RunEventsResponse(stages=stages, events=events, total_events=total_events)


@router.get("/runs/{run_id}", response_model=RunHistoryResponse)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
):
    """Get detailed run history including all failures."""
    run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=404,
            detail=make_error("RUN_NOT_FOUND", "Run not found", {"run_id": run_id}),
        )
    
    # Load connector name
    connector = db.query(Connector).filter_by(id=run.connector_id).first()
    connector_name = connector.name if connector else None
    
    # Load ALL failures for detail view (not limited)
    failures = (
        db.query(RunFailure)
        .filter(RunFailure.run_id == run_id)
        .order_by(RunFailure.created_at.asc())
        .all()
    )

    # Load endpoint logs ordered by execution_order
    endpoint_logs = (
        db.query(EndpointRunLog)
        .filter(EndpointRunLog.run_id == run_id)
        .order_by(EndpointRunLog.execution_order.asc())
        .all()
    )

    # Build endpoint lookup dict for name/path enrichment
    endpoint_ids = [log.endpoint_id for log in endpoint_logs]
    endpoints = (
        db.query(ConnectorEndpoint)
        .filter(ConnectorEndpoint.id.in_(endpoint_ids))
        .all()
    ) if endpoint_ids else []
    endpoint_lookup = {ep.id: ep for ep in endpoints}

    # Build canvas lookup for canvas_name enrichment
    from app.models.canvas import Canvas
    canvas_ids_in_logs = list({log.canvas_id for log in endpoint_logs if log.canvas_id})
    canvases = (
        db.query(Canvas)
        .filter(Canvas.id.in_(canvas_ids_in_logs))
        .all()
    ) if canvas_ids_in_logs else []
    canvas_lookup = {c.id: c.name for c in canvases}

    response = _to_response(run, failures, endpoint_logs, endpoint_lookup, include_payloads=True, canvas_lookup=canvas_lookup)
    response.connector_name = connector_name
    return response


@router.get("/connectors/{connector_id}/runs", response_model=Page[RunHistoryResponse])
def list_connector_runs(
    connector_id: str,
    db: Session = Depends(get_db),
    params: Params = Depends(),
    _user=Depends(require_role("admin", "operator")),
):
    """List runs for a specific connector with pagination."""
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )
    
    query = (
        select(RunHistory)
        .filter(RunHistory.connector_id == connector_id)
        .order_by(desc(RunHistory.started_at))
    )

    page = paginate(db, query, params)

    # Transform with failures
    items = []
    for run in page.items:
        failures = []
        if run.status in ["failed", "partial_success"]:
            failures_query = db.query(RunFailure).filter_by(run_id=run.id).limit(10).all()
            failures = failures_query

        response = _to_response(run, failures)
        response.connector_name = connector.name
        items.append(response)

    page.items = items
    return page


@router.post("/connectors/{connector_id}/runs", status_code=202)
def trigger_connector_run(
    connector_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
    canvas_id: Optional[str] = Query(None, description="Optional canvas ID for single-canvas sync"),
):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    # Guard: validate canvas if provided
    if canvas_id:
        from app.models.canvas import Canvas
        canvas = db.query(Canvas).filter_by(id=canvas_id, connector_id=connector_id).first()
        if not canvas:
            raise HTTPException(
                status_code=404,
                detail=make_error("CANVAS_NOT_FOUND", "Canvas not found", {"canvas_id": canvas_id}),
            )
        if not canvas.is_enabled:
            raise HTTPException(
                status_code=400,
                detail=make_error("CANVAS_DISABLED", "Canvas is disabled", {"canvas_id": canvas_id}),
            )

    # Guard: no enabled endpoints
    enabled_count = (
        db.query(ConnectorEndpoint)
        .filter(
            ConnectorEndpoint.connector_id == connector_id,
            ConnectorEndpoint.is_enabled == True,
        )
        .count()
    )
    if enabled_count == 0:
        raise HTTPException(
            status_code=400,
            detail=make_error(
                "NO_ENABLED_ENDPOINTS",
                "Connector has no enabled endpoints",
                {"connector_id": connector_id},
            ),
        )

    # Guard: CONN-02 endpoint mapping validity (canvas-aware)
    is_valid, invalid_endpoints = validate_endpoint_mappings(connector_id, db, canvas_id=canvas_id)
    if not is_valid:
        connector.is_valid_mappings = False
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=make_error(
                "INVALID_ENDPOINT_MAPPINGS",
                "One or more enabled endpoints are missing an identity mapping",
                {"invalid_endpoints": invalid_endpoints},
            ),
        )
    connector.is_valid_mappings = True
    db.commit()

    existing_run = (
        db.query(RunHistory)
        .filter(RunHistory.connector_id == connector_id, RunHistory.status == RunStatus.running)
        .first()
    )
    if existing_run:
        raise HTTPException(
            status_code=409,
            detail=make_error(
                "CONNECTOR_RUN_IN_PROGRESS",
                "Connector run already in progress",
                {"connector_id": connector_id},
            ),
        )

    run = create_run(connector_id, db=db)
    background_tasks.add_task(run_ingestion, run.id, canvas_id)
    return {"run_id": run.id, "status": RunStatus.running.value}
