"""Procrastinate task definitions for connector sync execution."""
import logging

import procrastinate

from app.worker import procrastinate_app

logger = logging.getLogger(__name__)


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
