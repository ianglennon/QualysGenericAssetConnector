from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from alembic import command
from alembic.config import Config
import logging

from app.core.settings import get_settings
from app.core.errors import http_exception_handler, validation_exception_handler

logger = logging.getLogger(__name__)


def run_migrations():
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    logger.info("Database migrations applied")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    run_migrations()
    # Seed admin user on first startup if users table is empty
    from app.db.session import SessionLocal
    from app.services.bootstrap_service import seed_admin_if_empty
    db = SessionLocal()
    try:
        seed_admin_if_empty(db)
    finally:
        db.close()
    
    # Initialize scheduler after migrations
    from app.scheduler.scheduler_service import init_scheduler, shutdown_scheduler
    init_scheduler(settings.database_url)
    
    yield
    
    # Shutdown scheduler on application shutdown
    shutdown_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Qualys Generic Asset Connector",
        version="1.0.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    from app.routers import auth, qualys, connectors, runs, schedules, field_mappings
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(qualys.router, prefix="/api/v1")
    app.include_router(connectors.router, prefix="/api/v1")
    app.include_router(runs.router, prefix="/api/v1")
    app.include_router(schedules.router, prefix="/api/v1")
    app.include_router(field_mappings.router, prefix="/api/v1")

    return app


app = create_app()
