"""Add must_change_password to users table

Revision ID: 006_must_change_password
Revises: 005_rbac_tables
Create Date: 2026-04-04
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_must_change_password"
down_revision: Union[str, None] = "005_rbac_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
