from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy import inspect as sa_inspect
from alembic import command
from alembic.config import Config
from fastapi_pagination import add_pagination
import logging
import sys
import time

from app.core.settings import get_settings
from app.core.errors import http_exception_handler, validation_exception_handler
from app.db.session import SessionLocal

_app_ready: bool = False

logger = logging.getLogger(__name__)

EXPECTED_TABLES = {
    "connectors",
    "connector_endpoints",
    "field_mappings",
    "qualys_config",
    "run_history",
    "run_failures",
    "run_events",
    "endpoint_run_logs",
    "users",
    "canvases",
    "canvas_endpoints",
}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request method, path, and response status for debugging."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %s (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response


def run_migrations():
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    logger.info("Database migrations applied")


def verify_db_integrity() -> None:
    """Verify all expected tables exist after migrations.

    If tables are missing: stamp Alembic to base, re-run migrations.
    If still missing after re-migration: log ERROR and sys.exit(1).
    """
    from app.db.session import engine
    inspector = sa_inspect(engine)
    actual = set(inspector.get_table_names())
    missing = EXPECTED_TABLES - actual

    if not missing:
        logger.info("DB integrity OK — all %d expected tables present", len(EXPECTED_TABLES))
        return

    logger.error(
        "DB integrity check FAILED — missing tables: %s. "
        "Stamping Alembic to base and re-running migrations.",
        sorted(missing),
    )
    cfg = Config("alembic.ini")
    command.stamp(cfg, "base")
    command.upgrade(cfg, "head")

    # Fresh inspector to avoid cached results
    inspector2 = sa_inspect(engine)
    still_missing = EXPECTED_TABLES - set(inspector2.get_table_names())
    if still_missing:
        logger.error(
            "Re-migration did NOT resolve missing tables: %s. "
            "Manual intervention required. Exiting.",
            sorted(still_missing),
        )
        sys.exit(1)

    logger.info("Re-migration successful — all expected tables now present.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app_ready
    settings = get_settings()
    run_migrations()
    verify_db_integrity()
    # Seed admin user on first startup if users table is empty
    from app.services.bootstrap_service import seed_admin_if_empty
    db = SessionLocal()
    try:
        seed_admin_if_empty(db)
    finally:
        db.close()

    # Initialize scheduler after migrations
    from app.scheduler.scheduler_service import init_scheduler, shutdown_scheduler
    init_scheduler(settings.database_url)

    _app_ready = True
    yield

    _app_ready = False
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
    app.add_middleware(RequestLoggingMiddleware)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    from app.routers import auth, qualys, connectors, runs, schedules, field_mappings, endpoints, canvases, canvas_endpoints
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(qualys.router, prefix="/api/v1")
    app.include_router(connectors.router, prefix="/api/v1")
    app.include_router(runs.router, prefix="/api/v1")
    app.include_router(schedules.router, prefix="/api/v1")
    app.include_router(field_mappings.router, prefix="/api/v1")
    app.include_router(endpoints.router, prefix="/api/v1")
    app.include_router(canvases.router, prefix="/api/v1")
    app.include_router(canvas_endpoints.router, prefix="/api/v1")

    @app.get("/health")
    def health_check():
        if not _app_ready:
            return JSONResponse(status_code=503, content={"status": "starting"})
        db_ok = False
        try:
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            db_ok = True
        except Exception:
            pass
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "db": "ok" if db_ok else "error"},
        )

    add_pagination(app)
    return app


app = create_app()
