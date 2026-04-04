"""Integration tests for Role CRUD API (ROLE-04, ROLE-05).

Uses shared conftest.py fixtures for DB session, client, and auth tokens.
"""
import pytest


class TestRoleCreate:
    """Tests for POST /api/v1/roles."""

    def test_create_role(self, client, admin_token):
        """Create a custom role with name and description."""
        resp = client.post(
            "/api/v1/roles",
            json={"name": "Custom Role", "description": "A test role"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Custom Role"
        assert data["description"] == "A test role"
        assert data["is_system"] is False
        assert data["permissions"] == []

    def test_create_role_duplicate_name_409(self, client, admin_token):
        """Duplicate role name returns 409 ROLE_NAME_EXISTS."""
        client.post(
            "/api/v1/roles",
            json={"name": "DupRole"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.post(
            "/api/v1/roles",
            json={"name": "DupRole"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "ROLE_NAME_EXISTS"


class TestRoleList:
    """Tests for GET /api/v1/roles."""

    def test_list_roles_includes_administrator(self, client, admin_token):
        """GET /roles always contains Administrator (seeded by admin_role fixture)."""
        resp = client.get(
            "/api/v1/roles",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert "Administrator" in names


class TestRoleGet:
    """Tests for GET /api/v1/roles/{id}."""

    def test_get_role_with_permissions(self, client, admin_token, admin_role):
        """GET /roles/{id} returns permissions list."""
        resp = client.get(
            f"/api/v1/roles/{admin_role.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "permissions" in data
        assert len(data["permissions"]) == 30  # ALL_PERMISSIONS count


class TestRolePermissions:
    """Tests for POST/DELETE /api/v1/roles/{id}/permissions."""

    def test_add_permission_to_role(self, client, admin_token):
        """Add a permission to a custom role."""
        # Create a custom role first
        create_resp = client.post(
            "/api/v1/roles",
            json={"name": "PermTestRole"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        role_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/roles/{role_id}/permissions",
            json={"permissions": ["connectors:read"]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert "connectors:read" in resp.json()["permissions"]

    def test_add_invalid_permission_422(self, client, admin_token):
        """Invalid permission string returns 422 PERMISSION_INVALID."""
        create_resp = client.post(
            "/api/v1/roles",
            json={"name": "InvalidPermRole"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        role_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/roles/{role_id}/permissions",
            json={"permissions": ["nonexistent:permission"]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "PERMISSION_INVALID"

    def test_remove_permission_from_role(self, client, admin_token):
        """Remove a permission from a custom role."""
        # Create role and add permission
        create_resp = client.post(
            "/api/v1/roles",
            json={"name": "RemovePermRole"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        role_id = create_resp.json()["id"]
        client.post(
            f"/api/v1/roles/{role_id}/permissions",
            json={"permissions": ["connectors:read", "connectors:create"]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Remove one permission
        resp = client.delete(
            f"/api/v1/roles/{role_id}/permissions/connectors:read",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert "connectors:read" not in resp.json()["permissions"]
        assert "connectors:create" in resp.json()["permissions"]


class TestSystemRoleProtection:
    """Tests for system role protection (ROLE-05)."""

    def test_cannot_edit_system_role(self, client, admin_token, admin_role):
        """PATCH Administrator role returns 403 ROLE_SYSTEM_PROTECTED."""
        resp = client.patch(
            f"/api/v1/roles/{admin_role.id}",
            json={"name": "Renamed Admin"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ROLE_SYSTEM_PROTECTED"

    def test_cannot_delete_system_role(self, client, admin_token, admin_role):
        """DELETE Administrator role returns 403 ROLE_SYSTEM_PROTECTED."""
        resp = client.delete(
            f"/api/v1/roles/{admin_role.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ROLE_SYSTEM_PROTECTED"

    def test_cannot_add_permission_to_system_role(self, client, admin_token, admin_role):
        """POST permissions to Administrator role returns 403 ROLE_SYSTEM_PROTECTED."""
        resp = client.post(
            f"/api/v1/roles/{admin_role.id}/permissions",
            json={"permissions": ["connectors:read"]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ROLE_SYSTEM_PROTECTED"


class TestRoleDeletion:
    """Tests for DELETE /api/v1/roles/{id}."""

    def test_cannot_delete_role_with_users(self, client, admin_token, test_role_id):
        """DELETE role with assigned users returns 409 ROLE_HAS_USERS."""
        # Assign a user to the test role
        client.post(
            "/api/v1/users",
            json={"email": "roleuser@test.com", "role_id": test_role_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        resp = client.delete(
            f"/api/v1/roles/{test_role_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "ROLE_HAS_USERS"

    def test_delete_empty_role(self, client, admin_token):
        """DELETE role with no users returns 204."""
        create_resp = client.post(
            "/api/v1/roles",
            json={"name": "EmptyRole"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        role_id = create_resp.json()["id"]

        resp = client.delete(
            f"/api/v1/roles/{role_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 204
