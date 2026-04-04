"""Procrastinate task definitions for connector sync execution."""
import logging
from datetime import datetime, timedelta

import procrastinate

from app.worker import procrastinate_app

logger = logging.getLogger(__name__)


def compute_next_run_at(
    interval_type: str,
    interval_value: int,
    from_time: datetime | None = None,
) -> datetime:
    """Compute next_run_at = from_time + interval.

    Used by both the poller (D-07) and schedule router (D-04).
    Uses datetime.utcnow() as base when from_time is None (consistent
    with existing created_at/updated_at patterns in codebase).
    """
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


@procrastinate_app.task(
    queue="syncs",
    retry=procrastinate.RetryStrategy(
        max_attempts=3,
        wait=30,
        linear_wait=30,
    ),
)
async def run_connector_sync(
    connector_id: str,
    run_id: str,
    canvas_id: str | None = None,
    triggered_by: str = "manual",
) -> None:
    """Execute connector sync via ingestion pipeline.

    Per D-06: The RunHistory record is created BEFORE deferral.
    This task receives an existing run_id and updates the same record.
    On retry, Procrastinate re-executes with the same arguments.
    """
    from app.services.ingestion_service import run_ingestion

    logger.info(
        "Executing sync task: connector=%s run=%s canvas=%s triggered_by=%s",
        connector_id, run_id, canvas_id, triggered_by,
    )
    await run_ingestion(run_id, canvas_id)
    logger.info("Sync task completed: connector=%s run=%s", connector_id, run_id)


@procrastinate_app.periodic(cron="* * * * *")
@procrastinate_app.task(queue="default")
async def poll_due_schedules(timestamp: int) -> None:
    """Poll for connectors with due schedules and defer sync jobs (D-01).

    Runs every 60 seconds. Queries connectors WHERE schedule_enabled=true
    AND next_run_at <= now(). Defers sync jobs and advances next_run_at
    immediately (D-07). Silent on empty polls (D-03).
    """
    from sqlalchemy import and_
    from app.db.session import SessionLocal
    from app.models.connector import Connector
    from app.services.ingestion_service import create_run
    from procrastinate.exceptions import AlreadyEnqueued

    now = datetime.utcnow()
    db = SessionLocal()
    try:
        due = db.query(Connector).filter(
            and_(
                Connector.schedule_enabled == True,  # noqa: E712
                Connector.next_run_at <= now,
            )
        ).all()

        if not due:
            return  # D-03: silent on empty polls

        logger.info("Poller found %d due connector(s)", len(due))

        for connector in due:
            # D-07: Advance next_run_at immediately (poller owns this column)
            # D-06: Uses now as base, skipping missed windows
            connector.next_run_at = compute_next_run_at(
                connector.interval_type, connector.interval_value, from_time=now
            )

            run = create_run(connector.id, db=db)

            try:
                await run_connector_sync.configure(
                    queueing_lock=f"connector_{connector.id}",
                    lock=f"connector_{connector.id}",
                ).defer_async(
                    connector_id=str(connector.id),
                    run_id=str(run.id),
                    triggered_by="schedule",
                )
            except AlreadyEnqueued:
                db.delete(run)
                logger.info(
                    "Connector %s already enqueued, skipping", connector.id
                )

        db.commit()
    finally:
        db.close()
