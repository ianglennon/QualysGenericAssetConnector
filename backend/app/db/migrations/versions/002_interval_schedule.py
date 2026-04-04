"""Drop cron_schedule, add interval columns

Revision ID: 002_interval_schedule
Revises: 001_baseline
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_interval_schedule"
down_revision: Union[str, None] = "001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("connectors", "cron_schedule")
    op.add_column("connectors", sa.Column("interval_type", sa.String(), nullable=True))
    op.add_column("connectors", sa.Column("interval_value", sa.Integer(), nullable=True))
    op.add_column("connectors", sa.Column("next_run_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("connectors", "next_run_at")
    op.drop_column("connectors", "interval_value")
    op.drop_column("connectors", "interval_type")
    op.add_column("connectors", sa.Column("cron_schedule", sa.String(), nullable=True))
