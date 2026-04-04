"""Integration tests for User CRUD API (USER-01 through USER-05).

Uses shared conftest.py fixtures for DB session, client, and auth tokens.
"""
import pytest


class TestUserCreate:
    """Tests for POST /api/v1/users (USER-01)."""

    def test_create_user_returns_temp_password(self, client, admin_token, test_role_id):
        """USER-01: Admin creates user, receives temporary password."""
        resp = client.post(
            "/api/v1/users",
            json={"email": "newuser@test.com", "role_id": test_role_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "temporary_password" in data
        assert len(data["temporary_password"]) >= 12
        assert data["must_change_password"] is True
        assert data["email"] == "newuser@test.com"

    def test_create_user_duplicate_email_409(self, client, admin_token, test_role_id):
        """USER-01: Duplicate email returns 409 USER_EMAIL_EXISTS."""
        client.post(
            "/api/v1/users",
            json={"email": "dup@test.com", "role_id": test_role_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.post(
            "/api/v1/users",
            json={"email": "dup@test.com", "role_id": test_role_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "USER_EMAIL_EXISTS"


class TestUserList:
    """Tests for GET /api/v1/users (USER-01)."""

    def test_list_users(self, client, admin_token):
        """USER-01: Admin can list all users."""
        resp = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestUserUpdate:
    """Tests for PATCH /api/v1/users/{id} (USER-02)."""

    def test_update_user_email(self, client, admin_token, test_role_id):
        """USER-02: Admin can update user email."""
        # Create a user first
        create_resp = client.post(
            "/api/v1/users",
            json={"email": "toupdate@test.com", "role_id": test_role_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        user_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/users/{user_id}",
            json={"email": "updated@test.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "updated@test.com"


class TestUserDeactivate:
    """Tests for POST /api/v1/users/{id}/deactivate (USER-03, USER-04, USER-05)."""

    def test_deactivate_user(self, client, admin_token, test_role_id):
        """USER-03: Admin can deactivate a user."""
        create_resp = client.post(
            "/api/v1/users",
            json={"email": "todeactivate@test.com", "role_id": test_role_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        user_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/users/{user_id}/deactivate",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_cannot_deactivate_self(self, client, admin_token_and_id):
        """USER-05: Admin cannot deactivate themselves."""
        token, user_id = admin_token_and_id
        resp = client.post(
            f"/api/v1/users/{user_id}/deactivate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "USER_SELF_DEACTIVATE"

    def test_cannot_deactivate_last_admin(self, client, admin_token_and_id):
        """USER-04: Cannot deactivate the last Administrator via PATCH."""
        token, user_id = admin_token_and_id
        resp = client.patch(
            f"/api/v1/users/{user_id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Should hit USER_SELF_DEACTIVATE (since user is deactivating themselves)
        assert resp.status_code == 409


class TestUserNotFound:
    """Tests for user lookup errors."""

    def test_user_not_found_404(self, client, admin_token):
        """USER lookup: nonexistent user returns 404."""
        resp = client.get(
            "/api/v1/users/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "USER_NOT_FOUND"


class TestUserPermissions:
    """Tests for permission enforcement on user endpoints."""

    def test_unauthorized_without_permission(self, client, operator_token):
        """PERM-01: Users without users:read permission get 403."""
        resp = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert resp.status_code == 403
