"""Schedule CRUD endpoints for connector scheduling."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from croniter import croniter

from app.db.session import get_db
from app.models.connector import Connector
from app.schemas.schedule import IntervalSchedule, IntervalType, ScheduleUpdate, ScheduleResponse
from app.core.security import require_role
from app.core.errors import make_error


router = APIRouter(prefix="/connectors", tags=["schedules"])


def interval_to_cron(interval: IntervalSchedule) -> str:
    """Convert interval picker selection to cron expression.

    Args:
        interval: IntervalSchedule with type and value

    Returns:
        Cron expression string (e.g., "0 */6 * * *" for every 6 hours)
    """
    if interval.interval_type == IntervalType.minutes:
        return f"*/{interval.interval_value} * * * *"
    elif interval.interval_type == IntervalType.hours:
        return f"0 */{interval.interval_value} * * *"
    elif interval.interval_type == IntervalType.days:
        return f"0 0 */{interval.interval_value} * *"
    elif interval.interval_type == IntervalType.weeks:
        # Every N weeks = every N*7 days
        return f"0 0 */{interval.interval_value * 7} * *"
    else:
        raise ValueError(f"Invalid interval type: {interval.interval_type}")


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
        connector.cron_schedule = None
        connector.schedule_enabled = False
        db.commit()
        db.refresh(connector)
        return ScheduleResponse(
            cron_schedule=None,
            schedule_enabled=False,
            execution_timeout=connector.execution_timeout,
            next_run_time=None,
        )

    # Convert interval to cron and validate
    cron = interval_to_cron(payload.interval)
    if not croniter.is_valid(cron):
        raise HTTPException(
            status_code=400,
            detail=make_error("INVALID_CRON", "Generated cron expression is invalid", {"cron": cron}),
        )

    # Update database
    connector.cron_schedule = cron
    connector.schedule_enabled = True
    if payload.execution_timeout is not None:
        connector.execution_timeout = payload.execution_timeout

    db.commit()
    db.refresh(connector)

    return ScheduleResponse(
        cron_schedule=connector.cron_schedule,
        schedule_enabled=connector.schedule_enabled,
        execution_timeout=connector.execution_timeout,
        next_run_time=None,
    )


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

    return ScheduleResponse(
        cron_schedule=connector.cron_schedule,
        schedule_enabled=connector.schedule_enabled,
        execution_timeout=connector.execution_timeout,
        next_run_time=None,
    )


@router.post("/{connector_id}/schedule/pause", response_model=ScheduleResponse, status_code=200)
def pause_schedule(
    connector_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Pause connector schedule without deleting it.

    Schedule can be resumed later. Admin-only endpoint.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    if not connector.cron_schedule:
        raise HTTPException(
            status_code=400,
            detail=make_error("NO_SCHEDULE", "Connector has no schedule to pause", {}),
        )

    # Update database
    connector.schedule_enabled = False
    db.commit()
    db.refresh(connector)

    return ScheduleResponse(
        cron_schedule=connector.cron_schedule,
        schedule_enabled=False,
        execution_timeout=connector.execution_timeout,
        next_run_time=None,  # Paused jobs have no next run
    )


@router.post("/{connector_id}/schedule/resume", response_model=ScheduleResponse, status_code=200)
def resume_schedule(
    connector_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Resume a paused schedule.

    Admin-only endpoint.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    if not connector.cron_schedule:
        raise HTTPException(
            status_code=400,
            detail=make_error("NO_SCHEDULE", "Connector has no schedule to resume", {}),
        )

    # Update database
    connector.schedule_enabled = True
    db.commit()
    db.refresh(connector)

    return ScheduleResponse(
        cron_schedule=connector.cron_schedule,
        schedule_enabled=True,
        execution_timeout=connector.execution_timeout,
        next_run_time=None,
    )


@router.delete("/{connector_id}/schedule", status_code=204)
def delete_schedule(
    connector_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    """Delete connector schedule.

    Removes schedule from database. Admin-only endpoint.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {"connector_id": connector_id}),
        )

    # Clear database
    connector.cron_schedule = None
    connector.schedule_enabled = False
    db.commit()
