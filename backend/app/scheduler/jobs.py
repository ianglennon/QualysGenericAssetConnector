"""Scheduler job execution functions.

Module-level functions required for SQLAlchemyJobStore serialization.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.db.session import SessionLocal
from app.models.run_history import RunHistory, RunStatus
from app.services.ingestion_service import run_ingestion

logger = logging.getLogger(__name__)


def run_connector_job(connector_id: str) -> None:
    """Execute connector ingestion job with overlap protection.
    
    Overlap guard: If a run is already active for this connector, skip execution
    and record a 'skipped' status in run history.
    
    Args:
        connector_id: UUID of the connector to run
    """
    db = SessionLocal()
    try:
        # Overlap guard: check for existing running job
        running = db.query(RunHistory).filter(
            RunHistory.connector_id == connector_id,
            RunHistory.status == RunStatus.running
        ).first()
        
        if running:
            # Record skipped execution
            skipped = RunHistory(
                connector_id=connector_id,
                status=RunStatus.skipped,
                triggered_by='scheduled',
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
            db.add(skipped)
            db.commit()
            logger.info(f"Skipped scheduled run for connector {connector_id} - previous run still active")
            return
        
        # Create new run history record with scheduled trigger
        run = RunHistory(
            connector_id=connector_id,
            status=RunStatus.running,
            triggered_by='scheduled',
            started_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
        
        logger.info(f"Starting scheduled run {run_id} for connector {connector_id}")
        
        # Execute ingestion asynchronously
        # APScheduler runs jobs in thread pool, so we need to create new event loop
        asyncio.run(run_ingestion(run_id))
        
        logger.info(f"Completed scheduled run {run_id} for connector {connector_id}")
    except Exception as exc:
        # Log error - APScheduler will handle retries per misfire policy
        logger.error(f"Error in scheduled job for connector {connector_id}: {exc}", exc_info=True)
    finally:
        db.close()
