"""Integration tests for schedule CRUD endpoints.

Uses shared conftest.py fixtures for DB and client.
Schedule routes are now interval-based (Phase 64: interval_type/interval_value columns).
"""
import pytest

from app.models.connector import Connector, AuthMethod


@pytest.fixture
def test_connector(db_session):
    """Create a test connector for schedule tests."""
    connector = Connector(
        name="Test Connector",
        base_url="https://api.example.com",
        auth_method=AuthMethod.bearer_token.value,
        encrypted_token="test_encrypted_token",
    )
    db_session.add(connector)
    db_session.flush()
    return connector


@pytest.fixture
def admin_headers(admin_token):
    """Return admin auth headers."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def operator_headers(operator_token):
    """Return operator auth headers."""
    return {"Authorization": f"Bearer {operator_token}"}


def test_set_schedule_success(client, admin_headers, test_connector):
    """Test setting a valid schedule via interval picker."""
    response = client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "hours",
                "interval_value": 6
            },
            "execution_timeout": 300
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["interval_type"] == "hours"
    assert data["interval_value"] == 6
    assert data["schedule_enabled"] is True
    assert data["execution_timeout"] == 300


def test_set_schedule_invalid_interval_too_small(client, admin_headers, test_connector):
    """Test setting schedule with interval value below minimum."""
    response = client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "minutes",
                "interval_value": 2  # Below minimum of 5
            }
        },
        headers=admin_headers,
    )

    assert response.status_code == 422  # Validation error


def test_set_schedule_invalid_interval_too_large(client, admin_headers, test_connector):
    """Test setting schedule with interval value above maximum."""
    response = client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "hours",
                "interval_value": 200  # Above maximum of 168
            }
        },
        headers=admin_headers,
    )

    assert response.status_code == 422  # Validation error


def test_get_schedule_enabled(client, admin_headers, test_connector):
    """Test retrieving an enabled schedule."""
    # Set a schedule first
    client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "days",
                "interval_value": 1
            }
        },
        headers=admin_headers,
    )

    # Get schedule
    response = client.get(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["interval_type"] == "days"
    assert data["interval_value"] == 1
    assert data["schedule_enabled"] is True


def test_get_schedule_no_schedule(client, admin_headers, test_connector):
    """Test retrieving schedule when none is set."""
    response = client.get(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["interval_type"] is None
    assert data["interval_value"] is None
    assert data["schedule_enabled"] is False
    assert data["next_run_at"] is None


def test_pause_schedule(client, admin_headers, test_connector):
    """Test pausing an active schedule."""
    # Set a schedule first
    client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "hours",
                "interval_value": 12
            }
        },
        headers=admin_headers,
    )

    # Pause schedule
    response = client.post(
        f"/api/v1/connectors/{test_connector.id}/schedule/pause",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["interval_type"] == "hours"
    assert data["interval_value"] == 12
    assert data["schedule_enabled"] is False
    assert data["next_run_at"] is None  # Paused jobs have no next run


def test_pause_schedule_no_schedule(client, admin_headers, test_connector):
    """Test pausing when no schedule exists."""
    response = client.post(
        f"/api/v1/connectors/{test_connector.id}/schedule/pause",
        headers=admin_headers,
    )

    assert response.status_code == 400


def test_resume_schedule(client, admin_headers, test_connector):
    """Test resuming a paused schedule."""
    # Set and pause schedule
    client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "weeks",
                "interval_value": 1
            }
        },
        headers=admin_headers,
    )
    client.post(
        f"/api/v1/connectors/{test_connector.id}/schedule/pause",
        headers=admin_headers,
    )

    # Resume schedule
    response = client.post(
        f"/api/v1/connectors/{test_connector.id}/schedule/resume",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schedule_enabled"] is True
    # next_run_at should be recomputed on resume
    assert data["next_run_at"] is not None


def test_delete_schedule(client, admin_headers, test_connector):
    """Test deleting a schedule."""
    # Set a schedule first
    client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "hours",
                "interval_value": 3
            }
        },
        headers=admin_headers,
    )

    # Delete schedule
    response = client.delete(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        headers=admin_headers,
    )

    assert response.status_code == 204

    # Verify via GET that schedule is cleared
    get_response = client.get(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        headers=admin_headers,
    )
    assert get_response.json()["interval_type"] is None


def test_clear_schedule_via_put(client, admin_headers, test_connector):
    """Test clearing schedule by setting interval to None."""
    # Set a schedule first
    client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "days",
                "interval_value": 7
            }
        },
        headers=admin_headers,
    )

    # Clear schedule
    response = client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": None
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["interval_type"] is None
    assert data["interval_value"] is None
    assert data["schedule_enabled"] is False


def test_schedule_rbac_operator_cannot_mutate(client, operator_headers, test_connector):
    """Test that operators cannot modify schedules."""
    # Operator cannot set schedule
    response = client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "hours",
                "interval_value": 6
            }
        },
        headers=operator_headers,
    )
    assert response.status_code == 403

    # Operator cannot pause
    response = client.post(
        f"/api/v1/connectors/{test_connector.id}/schedule/pause",
        headers=operator_headers,
    )
    assert response.status_code == 403

    # Operator cannot resume
    response = client.post(
        f"/api/v1/connectors/{test_connector.id}/schedule/resume",
        headers=operator_headers,
    )
    assert response.status_code == 403

    # Operator cannot delete
    response = client.delete(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        headers=operator_headers,
    )
    assert response.status_code == 403


def test_schedule_rbac_operator_can_view(client, operator_headers, test_connector, admin_headers):
    """Test that operators can view schedules."""
    # Admin sets schedule
    client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "hours",
                "interval_value": 4
            }
        },
        headers=admin_headers,
    )

    # Operator can view
    response = client.get(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        headers=operator_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["interval_type"] == "hours"
    assert data["interval_value"] == 4


def test_schedule_persists_in_database(client, admin_headers, test_connector, db_session):
    """Test that schedule persists in the database."""
    # Set a schedule
    client.put(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        json={
            "interval": {
                "interval_type": "hours",
                "interval_value": 8
            }
        },
        headers=admin_headers,
    )

    # Verify database state directly
    db_session.refresh(test_connector)
    assert test_connector.interval_type == "hours"
    assert test_connector.interval_value == 8
    assert test_connector.schedule_enabled is True

    # Verify can still retrieve schedule
    response = client.get(
        f"/api/v1/connectors/{test_connector.id}/schedule",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["interval_type"] == "hours"
    assert data["interval_value"] == 8
    assert data["schedule_enabled"] is True
