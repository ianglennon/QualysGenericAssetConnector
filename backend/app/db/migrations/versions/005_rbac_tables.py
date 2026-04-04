"""Add RBAC roles and role_permissions tables, migrate users.role to role_id FK.

Revision ID: 005_rbac_tables
Revises: 004_add_base_records_cols
Create Date: 2026-04-04
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
import uuid

revision: str = "005_rbac_tables"
down_revision: Union[str, None] = "004_add_base_records_cols"
branch_labels = None
depends_on = None

ADMIN_ROLE_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "qualys-connector.admin"))

ALL_PERMISSIONS = [
    "connectors:create", "connectors:read", "connectors:update", "connectors:delete",
    "connectors:toggle_enabled",
    "canvases:create", "canvases:read", "canvases:update", "canvases:delete",
    "schedules:create", "schedules:read", "schedules:update", "schedules:delete",
    "runs:create", "runs:read", "runs:update", "runs:delete",
    "runs:trigger_sync",
    "settings:create", "settings:read", "settings:update", "settings:delete",
    "users:create", "users:read", "users:update", "users:delete",
    "roles:create", "roles:read", "roles:update", "roles:delete",
]


def upgrade() -> None:
    # 1. Create roles table
    op.create_table(
        "roles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # 2. Create role_permissions table
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("role_id", sa.String(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission", sa.String(100), nullable=False),
        sa.UniqueConstraint("role_id", "permission", name="uq_role_permission"),
    )

    # 3. Index on role_permissions.role_id for FK lookups
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])

    # 4. Seed Administrator role
    bind = op.get_bind()
    now = sa.func.now()
    bind.execute(
        sa.text(
            "INSERT INTO roles (id, name, description, is_system, created_at, updated_at) "
            "VALUES (:id, :name, :description, :is_system, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {
            "id": ADMIN_ROLE_ID,
            "name": "Administrator",
            "description": "Built-in role with all permissions",
            "is_system": True,
        },
    )

    # 5. Seed all 30 permissions for Administrator
    for perm in ALL_PERMISSIONS:
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (id, role_id, permission) "
                "VALUES (:id, :role_id, :permission)"
            ),
            {
                "id": str(uuid.uuid4()),
                "role_id": ADMIN_ROLE_ID,
                "permission": perm,
            },
        )

    # 6. Add role_id column (nullable initially for backfill)
    op.add_column("users", sa.Column("role_id", sa.String(), sa.ForeignKey("roles.id"), nullable=True))

    # 7. Backfill: all existing users become Administrator
    bind.execute(
        sa.text("UPDATE users SET role_id = :role_id"),
        {"role_id": ADMIN_ROLE_ID},
    )

    # 8. Make role_id NOT NULL after backfill
    op.alter_column("users", "role_id", nullable=False)

    # 9. Drop old role enum column
    op.drop_column("users", "role")

    # 10. Drop PG enum type (critical for PostgreSQL)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # 1. Re-create userrole enum type
    sa.Enum("admin", "operator", name="userrole").create(op.get_bind(), checkfirst=True)

    # 2. Add back role column (nullable for backfill)
    op.add_column(
        "users",
        sa.Column("role", sa.Enum("admin", "operator", name="userrole"), nullable=True),
    )

    # 3. Backfill: all users were migrated to Administrator, restore as admin
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE users SET role = 'admin'"))

    # 4. Make role NOT NULL
    op.alter_column("users", "role", nullable=False)

    # 5. Drop role_id column
    op.drop_column("users", "role_id")

    # 6. Drop index
    op.drop_index("ix_role_permissions_role_id", "role_permissions")

    # 7. Drop role_permissions table
    op.drop_table("role_permissions")

    # 8. Drop roles table
    op.drop_table("roles")
