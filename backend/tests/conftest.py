"""Shared test fixtures for PostgreSQL transaction-rollback isolation.

Per D-01: Single conftest creates one PostgreSQL test database connection.
Per D-02: Tests connect to a real PostgreSQL container.
Per D-03: Separate test database (qualys_test) on the same PostgreSQL container.
Per D-04: Base.metadata.create_all() builds schema directly from models.
"""
import os
from contextlib import asynccontextmanager
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
from app.models.role import Role, RolePermission  # noqa: F401
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

    @asynccontextmanager
    async def _noop_procrastinate_lifecycle(settings):
        yield

    with (
        patch("app.main.run_migrations"),
        patch("app.main.verify_db_integrity"),
        patch("app.services.bootstrap_service.seed_admin_if_empty"),
        patch("app.main._procrastinate_lifecycle", _noop_procrastinate_lifecycle),
    ):
        with TestClient(fastapi_app, raise_server_exceptions=False) as c:
            yield c

    fastapi_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_role(db_session):
    """Seed an Administrator role for tests."""
    from app.models.role import Role, RolePermission
    from app.core.permissions import ALL_PERMISSIONS
    role = Role(name="Administrator", description="Test admin role", is_system=True)
    db_session.add(role)
    db_session.flush()
    for perm in ALL_PERMISSIONS:
        db_session.add(RolePermission(role_id=role.id, permission=perm))
    db_session.flush()
    return role


@pytest.fixture(scope="function")
def operator_role(db_session):
    """Seed an Operator role for tests (read-only permissions)."""
    from app.models.role import Role, RolePermission
    role = Role(name="Operator", description="Test operator role", is_system=False)
    db_session.add(role)
    db_session.flush()
    # Operator gets read permissions + runs:trigger_sync
    for resource in ["connectors", "canvases", "schedules", "runs", "settings"]:
        db_session.add(RolePermission(role_id=role.id, permission=f"{resource}:read"))
    db_session.add(RolePermission(role_id=role.id, permission="runs:trigger_sync"))
    db_session.flush()
    return role


@pytest.fixture(scope="function")
def admin_token(client, db_session, admin_role):
    """Create an admin user and return a valid JWT access token."""
    from app.services.auth_service import create_user
    create_user(db_session, "admin@test.com", "AdminPass12!!", role_id=admin_role.id)
    db_session.flush()
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "AdminPass12!!"
    })
    return resp.json()["access_token"]


@pytest.fixture(scope="function")
def operator_token(client, db_session, operator_role):
    """Create an operator user and return a valid JWT access token."""
    from app.services.auth_service import create_user
    create_user(db_session, "operator@test.com", "OperatorPass12!!", role_id=operator_role.id)
    db_session.flush()
    resp = client.post("/api/v1/auth/login", json={
        "email": "operator@test.com",
        "password": "OperatorPass12!!"
    })
    return resp.json()["access_token"]


@pytest.fixture(scope="function")
def admin_user(db_session, admin_role):
    """Seed an admin user and return the User object."""
    from app.services.auth_service import create_user
    user = create_user(db_session, "admin_fixture@test.com", "AdminPass12!!", role_id=admin_role.id)
    db_session.flush()
    return user


@pytest.fixture(scope="function")
def admin_user_id(admin_user):
    """Return the admin user's ID."""
    return admin_user.id


@pytest.fixture(scope="function")
def admin_token_and_id(client, db_session, admin_role):
    """Create admin user and return (token, user_id) tuple."""
    from app.services.auth_service import create_user
    user = create_user(db_session, "admin_tid@test.com", "AdminPass12!!", role_id=admin_role.id)
    db_session.flush()
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin_tid@test.com",
        "password": "AdminPass12!!"
    })
    return resp.json()["access_token"], user.id


@pytest.fixture(scope="function")
def test_role(db_session):
    """Seed a non-system role for testing user creation."""
    from app.models.role import Role
    role = Role(name="TestRole", description="Non-system test role", is_system=False)
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture(scope="function")
def test_role_id(test_role):
    """Return the test role's ID."""
    return test_role.id
