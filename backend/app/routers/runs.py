from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.errors import make_error
from app.core.security import require_role
from app.db.session import get_db
from app.models.connector import Connector
from app.models.run_history import RunHistory, RunFailure, RunStatus
from app.schemas.run_history import RunHistoryResponse, RunFailureSummary
from app.services.ingestion_service import create_run, run_ingestion

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


def _to_response(run: RunHistory, failures: list[RunFailure]) -> RunHistoryResponse:
    return RunHistoryResponse(
        id=run.id,
        connector_id=run.connector_id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        started_at=run.started_at,
        finished_at=run.finished_at,
        records_fetched=run.records_fetched,
        records_submitted=run.records_submitted,
        records_failed=run.records_failed,
        error_type=run.error_type,
        error_message=run.error_message,
        error_context=run.error_context,
        failures=_map_failures(failures),
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


@router.get("/runs", response_model=list[RunHistoryResponse])
def list_runs(
    db: Session = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
):
    runs = db.query(RunHistory).order_by(RunHistory.started_at.desc()).all()
    failures_map = _fetch_failures_by_run(db, [run.id for run in runs])
    return [_to_response(run, failures_map.get(run.id, [])) for run in runs]


@router.get("/runs/{run_id}", response_model=RunHistoryResponse)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
):
    run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=404,
            detail=make_error("RUN_NOT_FOUND", "Run not found", {"run_id": run_id}),
        )
    failures = (
        db.query(RunFailure)
        .filter(RunFailure.run_id == run_id)
        .order_by(RunFailure.created_at.asc())
        .all()
    )
    return _to_response(run, failures)


@router.get("/connectors/{connector_id}/runs", response_model=list[RunHistoryResponse])
def list_connector_runs(
    connector_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )
    runs = (
        db.query(RunHistory)
        .filter(RunHistory.connector_id == connector_id)
        .order_by(RunHistory.started_at.desc())
        .all()
    )
    failures_map = _fetch_failures_by_run(db, [run.id for run in runs])
    return [_to_response(run, failures_map.get(run.id, [])) for run in runs]


@router.post("/connectors/{connector_id}/runs", status_code=202)
def trigger_connector_run(
    connector_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user=Depends(require_role("admin", "operator")),
):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

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

    run = create_run(connector_id)
    background_tasks.add_task(run_ingestion, run.id)
    return {"run_id": run.id, "status": RunStatus.running.value}
