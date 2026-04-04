"""Schedule API integration tests (SM-01, SM-02, SM-04).

Uses shared conftest fixtures (db_session, client, admin_token) which handle
PostgreSQL test database and procrastinate lifecycle mocking.
"""
import pytest


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
    assert "cron_schedule" not in data


def test_clear_schedule(client, admin_token):
    """SM-02: Setting interval=None clears the schedule."""
    cid = _create_connector(client, admin_token)
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
    resp = client.post(
        f"/api/v1/connectors/{cid}/schedule/pause",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["schedule_enabled"] is False
    assert resp.json()["next_run_at"] is None

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
