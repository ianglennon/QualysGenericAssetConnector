"""Scheduler service with APScheduler integration.

Manages BackgroundScheduler lifecycle and job reconciliation on startup.
"""
from __future__ import annotations

import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger

from app.db.session import SessionLocal
from app.models.connector import Connector

logger = logging.getLogger(__name__)

# Module-level singleton
scheduler: BackgroundScheduler | None = None


def init_scheduler(database_url: str) -> None:
    """Initialize and start the scheduler with SQLAlchemy job store.
    
    Args:
        database_url: Database URL for SQLAlchemyJobStore persistence
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler already initialized")
        return
    
    # Configure job store to use existing database
    jobstores = {
        'default': SQLAlchemyJobStore(url=database_url)
    }
    
    # Initialize scheduler with overlap prevention and grace period
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        job_defaults={
            'coalesce': True,         # Combine missed runs into one
            'max_instances': 1,        # Prevent parallel execution
            'misfire_grace_time': 60   # 60 second grace period on startup
        },
        timezone=pytz.utc  # Use UTC for all scheduled runs
    )
    
    # Reconcile jobs from database on startup
    reconcile_jobs_on_startup(scheduler)
    
    # Start scheduler (non-blocking for BackgroundScheduler)
    scheduler.start()
    logger.info("Scheduler started successfully")


def shutdown_scheduler() -> None:
    """Shutdown scheduler gracefully."""
    global scheduler
    
    if scheduler is not None:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shutdown complete")
        scheduler = None


def get_scheduler() -> BackgroundScheduler:
    """Get the scheduler singleton.
    
    Returns:
        BackgroundScheduler instance
        
    Raises:
        RuntimeError: If scheduler has not been initialized
    """
    if scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")
    return scheduler


def reconcile_jobs_on_startup(scheduler: BackgroundScheduler) -> None:
    """Reconcile scheduler jobs with database state on startup.
    
    This ensures:
    - Jobs in scheduler match jobs in database (no drift)
    - Orphaned scheduler jobs are removed
    - Database schedules are loaded into scheduler
    
    Note: If schedule columns don't exist yet (pre-migration), this is a no-op.
    The migration in 04-02 will add the columns, and scheduler will work after that.
    
    Args:
        scheduler: BackgroundScheduler instance to reconcile
    """
    from app.scheduler.jobs import run_connector_job
    from sqlalchemy.exc import OperationalError
    
    db = SessionLocal()
    try:
        # Get all connectors with schedules enabled
        # This will fail if columns don't exist yet (pre-migration in 04-02)
        try:
            enabled_connectors = db.query(Connector).filter(
                Connector.schedule_enabled == True,
                Connector.cron_schedule.isnot(None)
            ).all()
        except OperationalError as e:
            # Columns don't exist yet - migration hasn't run
            logger.info("Schedule columns not yet migrated - skipping job reconciliation")
            db.rollback()  # Rollback the failed transaction
            return
        
        # Build set of expected job IDs
        expected_job_ids = {f"connector_{c.id}" for c in enabled_connectors}
        
        # Remove scheduler jobs not in database
        for job in scheduler.get_jobs():
            if job.id not in expected_job_ids:
                scheduler.remove_job(job.id)
                logger.info(f"Removed orphaned job: {job.id}")
        
        # Add/update jobs from database
        for connector in enabled_connectors:
            job_id = f"connector_{connector.id}"
            try:
                scheduler.add_job(
                    func=run_connector_job,
                    trigger=CronTrigger.from_crontab(connector.cron_schedule),
                    id=job_id,
                    kwargs={'connector_id': str(connector.id)},
                    replace_existing=True  # Update if exists
                )
                logger.info(f"Registered job: {job_id} with schedule: {connector.cron_schedule}")
            except Exception as e:
                logger.error(f"Failed to register job {job_id}: {e}")
        
        logger.info(f"Job reconciliation complete: {len(expected_job_ids)} jobs loaded")
    finally:
        db.close()
