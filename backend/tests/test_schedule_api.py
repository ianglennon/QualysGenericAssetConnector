"""Schedule API integration tests (SM-01, SM-02, SM-04)."""
import os
import sys
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_schedule_api.db")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import create_app
from app.db.session import SessionLocal
from app.services.auth_service import create_user
from app.models.user import UserRole


@pytest.fixture(scope="module")
def client():
    db_path = os.path.abspath("test_schedule_api.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    app = create_app()
    with TestClient(app) as c:
        yield c
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="module")
def admin_token(client):
    db = SessionLocal()
    create_user(db, "schedapi_admin@test.com", "AdminPass12!", UserRole.admin)
    db.close()
    resp = client.post("/api/v1/auth/login", json={"email": "schedapi_admin@test.com", "password": "AdminPass12!"})
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_connector(client, token):
    """Helper: create a connector and return its ID."""
    resp = client.post(
        "/api/v1/connectors/",
        json={
            "name": "Test Connector",
            "base_url": "https://example.com/api",
            "auth_method": "bearer_token",
            "credentials": {"token": "test-token"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_connector_has_interval_columns(client, admin_token, db_session):
    """SM-01: Connector model has interval_type, interval_value, next_run_at."""
    from app.models.connector import Connector
    cid = _create_connector(client, admin_token)
    connector = db_session.query(Connector).filter_by(id=cid).first()
    assert hasattr(connector, "interval_type")
    assert hasattr(connector, "interval_value")
    assert hasattr(connector, "next_run_at")
    assert not hasattr(connector, "cron_schedule")


def test_connector_no_cron_schedule(client, admin_token, db_session):
    """SM-01: cron_schedule column removed."""
    from app.models.connector import Connector
    columns = [c.name for c in Connector.__table__.columns]
    assert "cron_schedule" not in columns
    assert "interval_type" in columns
    assert "interval_value" in columns
    assert "next_run_at" in columns


def test_set_schedule(client, admin_token):
    """SM-02: PUT /schedule writes interval columns directly."""
    cid = _create_connector(client, admin_token)
    resp = client.put(
        f"/api/v1/connectors/{cid}/schedule",
        json={"interval": {"interval_type": "hours", "interval_value": 6}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["interval_type"] == "hours"
    assert data["interval_value"] == 6
    assert data["schedule_enabled"] is True
    assert data["next_run_at"] is not None


def test_schedule_response_fields(client, admin_token):
    """SM-04: Response includes interval_type, interval_value, schedule_enabled, next_run_at."""
    cid = _create_connector(client, admin_token)
    # Set a schedule first
    client.put(
        f"/api/v1/connectors/{cid}/schedule",
        json={"interval": {"interval_type": "days", "interval_value": 1}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get(
        f"/api/v1/connectors/{cid}/schedule",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "interval_type" in data
    assert "interval_value" in data
    assert "schedule_enabled" in data
    assert "next_run_at" in data
    # Must NOT have cron_schedule
    assert "cron_schedule" not in data


def test_clear_schedule(client, admin_token):
    """SM-02: Setting interval=None clears the schedule."""
    cid = _create_connector(client, admin_token)
    # Set then clear
    client.put(
        f"/api/v1/connectors/{cid}/schedule",
        json={"interval": {"interval_type": "hours", "interval_value": 1}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.put(
        f"/api/v1/connectors/{cid}/schedule",
        json={"interval": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["interval_type"] is None
    assert data["interval_value"] is None
    assert data["schedule_enabled"] is False
    assert data["next_run_at"] is None


def test_pause_resume_schedule(client, admin_token):
    """SM-02: Pause clears next_run_at, resume recomputes it (D-04)."""
    cid = _create_connector(client, admin_token)
    client.put(
        f"/api/v1/connectors/{cid}/schedule",
        json={"interval": {"interval_type": "hours", "interval_value": 2}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Pause
    resp = client.post(
        f"/api/v1/connectors/{cid}/schedule/pause",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["schedule_enabled"] is False
    assert resp.json()["next_run_at"] is None

    # Resume
    resp = client.post(
        f"/api/v1/connectors/{cid}/schedule/resume",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["schedule_enabled"] is True
    assert resp.json()["next_run_at"] is not None


def test_delete_schedule(client, admin_token):
    """SM-02: DELETE clears all schedule columns."""
    cid = _create_connector(client, admin_token)
    client.put(
        f"/api/v1/connectors/{cid}/schedule",
        json={"interval": {"interval_type": "minutes", "interval_value": 15}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.delete(
        f"/api/v1/connectors/{cid}/schedule",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204


def test_connector_response_includes_schedule_fields(client, admin_token):
    """SM-04 / D-11: ConnectorResponse includes inline schedule fields."""
    cid = _create_connector(client, admin_token)
    resp = client.get(
        f"/api/v1/connectors/{cid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "interval_type" in data
    assert "interval_value" in data
    assert "schedule_enabled" in data
    assert "next_run_at" in data
