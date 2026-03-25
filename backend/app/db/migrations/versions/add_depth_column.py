"""add canvas_id, child_requests, and depth columns to endpoint_run_logs

Revision ID: e5a613d04e25
Revises: a1b2c3d4e5f6
Create Date: 2026-03-25 16:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a613d04e25'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        batch_op.add_column(sa.Column("canvas_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("child_requests_total", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("child_requests_failed", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("child_requests_skipped", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("depth", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        batch_op.drop_column("depth")
        batch_op.drop_column("child_requests_skipped")
        batch_op.drop_column("child_requests_failed")
        batch_op.drop_column("child_requests_total")
        batch_op.drop_column("canvas_id")
