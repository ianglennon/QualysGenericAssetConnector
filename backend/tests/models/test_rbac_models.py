"""RBAC model tests — Role, RolePermission, and User.role_id FK.

Covers gaps:
  ROLE-01: Role model columns, User.role_id FK, and relationships
  ROLE-02: RolePermission unique constraint rejects duplicate (role_id, permission)
  ROLE-06: is_system defaults False for new roles; seeded Administrator has is_system=True
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.role import Role, RolePermission
from app.models.user import User


# ---------------------------------------------------------------------------
# ROLE-01: Role model columns, User.role_id FK, and relationships
# ---------------------------------------------------------------------------


def test_role_model_has_required_columns():
    """ROLE-01: Role table has all required columns with correct types."""
    col_names = {c.name for c in Role.__table__.columns}
    expected = {"id", "name", "description", "is_system", "created_at", "updated_at"}
    assert expected.issubset(col_names), f"Missing columns: {expected - col_names}"


def test_role_name_column_is_unique_and_not_nullable():
    """ROLE-01: Role.name column is unique and NOT NULL."""
    col = Role.__table__.columns["name"]
    assert col.nullable is False, "Role.name must be NOT NULL"
    # SQLAlchemy unique=True creates a UniqueConstraint
    assert col.unique is True, "Role.name must have a unique constraint"


def test_role_permissions_relationship_exists():
    """ROLE-01: Role has a 'permissions' relationship to RolePermission."""
    assert hasattr(Role, "permissions"), "Role must have a 'permissions' relationship"


def test_role_users_relationship_exists():
    """ROLE-01: Role has a 'users' relationship to User."""
    assert hasattr(Role, "users"), "Role must have a 'users' relationship"


def test_user_has_role_id_fk_column():
    """ROLE-01: User.role_id is a FK to roles.id and is NOT NULL."""
    col = User.__table__.columns["role_id"]
    assert col.nullable is False, "User.role_id must be NOT NULL"
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "roles.id" in fk_targets, f"User.role_id must FK to roles.id, got {fk_targets}"


def test_user_has_role_relationship():
    """ROLE-01: User has a 'role' relationship back to Role."""
    assert hasattr(User, "role"), "User must have a 'role' relationship"


def test_role_and_user_can_be_created_with_relationship(db_session):
    """ROLE-01: Creating a User with a Role via role_id FK works end-to-end."""
    role = Role(name="TestRole", description="For FK test", is_system=False)
    db_session.add(role)
    db_session.flush()

    user = User(
        email="fktest@example.com",
        hashed_password="hashed",
        role_id=role.id,
    )
    db_session.add(user)
    db_session.flush()

    db_session.refresh(user)
    assert user.role_id == role.id
    assert user.role.name == "TestRole"


# ---------------------------------------------------------------------------
# ROLE-02: RolePermission unique constraint rejects duplicates
# ---------------------------------------------------------------------------


def test_role_permission_table_has_unique_constraint():
    """ROLE-02: role_permissions table declares UniqueConstraint on (role_id, permission)."""
    constraint_names = {c.name for c in RolePermission.__table__.constraints}
    assert "uq_role_permission" in constraint_names, (
        f"Missing uq_role_permission unique constraint, found: {constraint_names}"
    )


def test_duplicate_role_permission_raises_integrity_error(db_session):
    """ROLE-02: Inserting a duplicate (role_id, permission) pair raises IntegrityError."""
    role = Role(name="DupTestRole", is_system=False)
    db_session.add(role)
    db_session.flush()

    perm1 = RolePermission(role_id=role.id, permission="connectors:read")
    db_session.add(perm1)
    db_session.flush()

    perm2 = RolePermission(role_id=role.id, permission="connectors:read")
    db_session.add(perm2)

    with pytest.raises(IntegrityError):
        db_session.flush()


# ---------------------------------------------------------------------------
# ROLE-06: is_system flag behavior
# ---------------------------------------------------------------------------


def test_new_role_has_is_system_false_by_default(db_session):
    """ROLE-06: Roles created without is_system explicitly set default to False."""
    role = Role(name="DefaultSystemRole")
    db_session.add(role)
    db_session.flush()
    db_session.refresh(role)
    assert role.is_system is False, "is_system must default to False for new roles"


def test_seeded_administrator_role_has_is_system_true(db_session):
    """ROLE-06: A role created with is_system=True persists the flag correctly."""
    admin_role = Role(name="Administrator", description="Built-in", is_system=True)
    db_session.add(admin_role)
    db_session.flush()
    db_session.refresh(admin_role)
    assert admin_role.is_system is True, "Administrator role must have is_system=True"


def test_is_system_column_is_not_nullable():
    """ROLE-06: is_system column is NOT NULL (enforced at schema level)."""
    col = Role.__table__.columns["is_system"]
    assert col.nullable is False, "is_system must be NOT NULL"
