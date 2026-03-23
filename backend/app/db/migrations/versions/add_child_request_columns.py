"""add child_requests columns to endpoint_run_logs

Revision ID: d49b02c03d14
Revises: b2c3d4e5f6a7
Create Date: 2026-03-23 23:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd49b02c03d14'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        batch_op.add_column(sa.Column("child_requests_total", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("child_requests_failed", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("child_requests_skipped", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        batch_op.drop_column("child_requests_skipped")
        batch_op.drop_column("child_requests_failed")
        batch_op.drop_column("child_requests_total")
