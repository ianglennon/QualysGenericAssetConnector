"""Shared test fixtures for PostgreSQL transaction-rollback isolation.

Per D-01: Single conftest creates one PostgreSQL test database connection.
Per D-02: Tests connect to a real PostgreSQL container.
Per D-03: Separate test database (qualys_test) on the same PostgreSQL container.
Per D-04: Base.metadata.create_all() builds schema directly from models.
"""
import os
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Test database URL -- points to qualys_test, NOT qualys
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://qualys:qualys@db:5432/qualys_test"
)

from app.db.base import Base

# Import ALL models so Base.metadata is complete for create_all()
from app.models.user import User  # noqa: F401
from app.models.connector import Connector  # noqa: F401
from app.models.connector_endpoint import ConnectorEndpoint  # noqa: F401
from app.models.canvas import Canvas  # noqa: F401
from app.models.canvas_endpoint import CanvasEndpoint  # noqa: F401
from app.models.field_mapping import FieldMapping  # noqa: F401
from app.models.qualys_config import QualysConfig  # noqa: F401
from app.models.run_history import RunHistory, RunFailure, EndpointRunLog  # noqa: F401
from app.models.run_event import RunEvent  # noqa: F401


@pytest.fixture(scope="session")
def engine():
    """Create engine once for entire test session, build all tables."""
    eng = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    """Each test gets a transaction that rolls back after the test.

    Uses nested savepoints so that application code calling session.commit()
    commits the SAVEPOINT, not the outer transaction.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient with get_db overridden to use the rollback session.

    Patches lifespan side effects (migrations, admin seed, scheduler)
    to prevent them from running during tests.
    """
    from app.main import app as fastapi_app
    from app.db.session import get_db

    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    with (
        patch("app.main.run_migrations"),
        patch("app.main.verify_db_integrity"),
        patch("app.services.bootstrap_service.seed_admin_if_empty"),
        patch("app.scheduler.scheduler_service.init_scheduler"),
        patch("app.scheduler.scheduler_service.shutdown_scheduler"),
    ):
        with TestClient(fastapi_app, raise_server_exceptions=False) as c:
            yield c

    fastapi_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_token(client, db_session):
    """Create an admin user and return a valid JWT access token."""
    from app.services.auth_service import create_user
    from app.models.user import UserRole
    create_user(db_session, "admin@test.com", "AdminPass12!!", UserRole.admin)
    db_session.flush()
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "AdminPass12!!"
    })
    return resp.json()["access_token"]


@pytest.fixture(scope="function")
def operator_token(client, db_session):
    """Create an operator user and return a valid JWT access token."""
    from app.services.auth_service import create_user
    from app.models.user import UserRole
    create_user(db_session, "operator@test.com", "OperatorPass12!!", UserRole.operator)
    db_session.flush()
    resp = client.post("/api/v1/auth/login", json={
        "email": "operator@test.com",
        "password": "OperatorPass12!!"
    })
    return resp.json()["access_token"]
