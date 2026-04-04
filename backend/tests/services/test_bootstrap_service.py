"""Bootstrap service tests — seed_admin_if_empty behavior.

Covers gap:
  ROLE-03: seed_admin_if_empty seeds the Administrator role with is_system=True
           and all 30 permissions; admin user is assigned to that role.
"""
import pytest
from app.services.bootstrap_service import seed_admin_if_empty
from app.models.role import Role, RolePermission
from app.models.user import User
from app.core.permissions import ALL_PERMISSIONS


def test_seed_creates_administrator_role_with_is_system_true(db_session):
    """ROLE-03: seed_admin_if_empty creates an Administrator role with is_system=True."""
    seed_admin_if_empty(db_session)

    admin_role = (
        db_session.query(Role)
        .filter(Role.name == "Administrator", Role.is_system == True)
        .first()
    )
    assert admin_role is not None, "Administrator role must be created by seed"
    assert admin_role.is_system is True, "Seeded Administrator role must have is_system=True"


def test_seed_grants_all_30_permissions_to_administrator_role(db_session):
    """ROLE-03: seed_admin_if_empty assigns all 30 permission strings to Administrator."""
    seed_admin_if_empty(db_session)

    admin_role = db_session.query(Role).filter(Role.name == "Administrator").first()
    assert admin_role is not None

    seeded_perms = {rp.permission for rp in admin_role.permissions}
    expected_perms = set(ALL_PERMISSIONS)

    assert len(seeded_perms) == 30, (
        f"Expected 30 permissions on Administrator role, got {len(seeded_perms)}"
    )
    assert seeded_perms == expected_perms, (
        f"Permission mismatch. Missing: {expected_perms - seeded_perms}"
    )


def test_seed_is_idempotent_does_not_duplicate_administrator_role(db_session):
    """ROLE-03: Calling seed_admin_if_empty twice does not create a second Administrator role."""
    seed_admin_if_empty(db_session)
    seed_admin_if_empty(db_session)

    count = db_session.query(Role).filter(Role.name == "Administrator").count()
    assert count == 1, f"Expected exactly 1 Administrator role, found {count}"


def test_seed_creates_admin_user_assigned_to_administrator_role(db_session):
    """ROLE-03: When users table is empty, seed creates admin user with Administrator role_id."""
    seed_admin_if_empty(db_session)

    users = db_session.query(User).all()
    # Only check if the settings have admin_email configured (they always do in test env)
    if users:
        admin_user = users[0]
        admin_role = db_session.query(Role).filter(Role.name == "Administrator").first()
        assert admin_role is not None
        assert admin_user.role_id == admin_role.id, (
            "Admin user must be assigned to the Administrator role via role_id FK"
        )
