"""Schedule CRUD endpoints for connector scheduling.

Interval-based scheduling (Phase 64): writes interval_type/interval_value
directly to Connector columns. No cron conversion needed.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.connector import Connector
from app.schemas.schedule import ScheduleUpdate, ScheduleResponse
from app.core.security import require_role
from app.core.errors import make_error


router = APIRouter(prefix="/connectors", tags=["schedules"])


def compute_next_run_at(
    interval_type: str,
    interval_value: int,
    from_time: datetime | None = None,
) -> datetime:
    """Compute next_run_at = from_time + interval (D-04)."""
    base = from_time or datetime.utcnow()
    deltas = {
        "minutes": timedelta(minutes=interval_value),
        "hours": timedelta(hours=interval_value),
        "days": timedelta(days=interval_value),
        "weeks": timedelta(weeks=interval_value),
    }
    delta = deltas.get(interval_type)
    if not delta:
        raise ValueError(f"Unknown interval_type: {interval_type}")
    return base + delta


def _schedule_response(connector: Connector) -> ScheduleResponse:
    """Build ScheduleResponse from Connector columns (DRY helper)."""
    return ScheduleResponse(
        interval_type=connector.interval_type,
        interval_value=connector.interval_value,
        schedule_enabled=connector.schedule_enabled,
        execution_timeout=connector.execution_timeout,
        next_run_at=connector.next_run_at.isoformat() if connector.next_run_at else None,
    )


@router.put("/{connector_id}/schedule", response_model=ScheduleResponse)
def set_schedule(
    connector_id: str,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Set or update connector schedule.

    Set interval to None to clear the schedule.
    Admin-only endpoint.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    # Clear schedule if interval is None
    if payload.interval is None:
        connector.interval_type = None
        connector.interval_value = None
        connector.schedule_enabled = False
        connector.next_run_at = None
        db.commit()
        db.refresh(connector)
        return _schedule_response(connector)

    # Write interval columns directly (no cron conversion)
    connector.interval_type = payload.interval.interval_type.value
    connector.interval_value = payload.interval.interval_value
    connector.schedule_enabled = True
    connector.next_run_at = compute_next_run_at(
        connector.interval_type, connector.interval_value
    )

    if payload.execution_timeout is not None:
        connector.execution_timeout = payload.execution_timeout

    db.commit()
    db.refresh(connector)
    return _schedule_response(connector)


@router.get("/{connector_id}/schedule", response_model=ScheduleResponse)
def get_schedule(
    connector_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_role("operator")),  # Admin or operator can view
):
    """Get connector schedule status.

    Returns schedule configuration and next run time if enabled.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    return _schedule_response(connector)


@router.post("/{connector_id}/schedule/pause", response_model=ScheduleResponse, status_code=200)
def pause_schedule(
    connector_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Pause connector schedule without deleting it.

    Schedule can be resumed later. Admin-only endpoint.
    Clears next_run_at on pause per D-04.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    if not connector.interval_type:
        raise HTTPException(
            status_code=400,
            detail=make_error("NO_SCHEDULE", "Connector has no schedule to pause", {}),
        )

    # Update database — clear next_run_at on pause (D-04)
    connector.schedule_enabled = False
    connector.next_run_at = None
    db.commit()
    db.refresh(connector)

    return _schedule_response(connector)


@router.post("/{connector_id}/schedule/resume", response_model=ScheduleResponse, status_code=200)
def resume_schedule(
    connector_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Resume a paused schedule.

    Recomputes next_run_at from interval on resume per D-04.
    Admin-only endpoint.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    if not connector.interval_type:
        raise HTTPException(
            status_code=400,
            detail=make_error("NO_SCHEDULE", "Connector has no schedule to resume", {}),
        )

    # Update database — recompute next_run_at on resume (D-04)
    connector.schedule_enabled = True
    connector.next_run_at = compute_next_run_at(
        connector.interval_type, connector.interval_value
    )
    db.commit()
    db.refresh(connector)

    return _schedule_response(connector)


@router.delete("/{connector_id}/schedule", status_code=204)
def delete_schedule(
    connector_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Delete connector schedule.

    Clears all schedule columns. Admin-only endpoint.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    # Clear all schedule columns
    connector.interval_type = None
    connector.interval_value = None
    connector.schedule_enabled = False
    connector.next_run_at = None
    db.commit()
