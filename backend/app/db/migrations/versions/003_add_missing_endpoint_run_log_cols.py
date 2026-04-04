"""Add missing canvas_endpoint_id and endpoint_role to endpoint_run_logs

Revision ID: 003_add_missing_erl_cols
Revises: 002_interval_schedule
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_add_missing_erl_cols"
down_revision: Union[str, None] = "002_interval_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("endpoint_run_logs", sa.Column("canvas_endpoint_id", sa.String(), nullable=True))
    op.add_column("endpoint_run_logs", sa.Column("endpoint_role", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("endpoint_run_logs", "endpoint_role")
    op.drop_column("endpoint_run_logs", "canvas_endpoint_id")
