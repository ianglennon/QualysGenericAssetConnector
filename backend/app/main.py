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
    # Admin seed happens in Phase 1 plan 02 when User model exists
    yield


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

    # Routers added in subsequent plans
    # from app.routers import auth, qualys
    # app.include_router(auth.router, prefix="/api/v1")

    return app


app = create_app()
