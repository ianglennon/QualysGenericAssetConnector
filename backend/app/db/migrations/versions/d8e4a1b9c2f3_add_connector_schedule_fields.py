"""add_connector_schedule_fields

Revision ID: d8e4a1b9c2f3
Revises: f3b5a2c8b7c1
Create Date: 2026-02-20 21:00:00.000000

Adds scheduling fields to connectors table:
- cron_schedule: stores cron expression for scheduled runs
- schedule_enabled: boolean flag to enable/disable schedule without deletion
- execution_timeout: per-connector timeout override in seconds

Adds triggered_by column to run_history:
- tracks whether run was 'manual' (default) or 'scheduled'

Updates run_history.status enum to include 'skipped' value:
- skipped status used when overlap guard prevents execution
- Note: SQLite stores enum as TEXT with check constraint, so new value just needs documentation

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8e4a1b9c2f3"
down_revision: Union[str, None] = "95e9f5dc1f3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add scheduling columns to connectors table
    op.add_column("connectors", sa.Column("cron_schedule", sa.String(), nullable=True))
    op.add_column(
        "connectors",
        sa.Column("schedule_enabled", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("connectors", sa.Column("execution_timeout", sa.Integer(), nullable=True))

    # Add triggered_by column to run_history table
    op.add_column(
        "run_history",
        sa.Column("triggered_by", sa.String(), nullable=False, server_default="manual"),
    )

    # Update status enum to include 'skipped' value
    # SQLite doesn't support ALTER TYPE for enums, but the enum is stored as TEXT with check constraint
    # The Pydantic RunStatus enum already includes 'skipped' (added in 04-01)
    # Existing check constraint will validate against Python enum values
    # No schema change needed - just documenting the new valid value


def downgrade() -> None:
    # Remove added columns in reverse order
    op.drop_column("run_history", "triggered_by")
    op.drop_column("connectors", "execution_timeout")
    op.drop_column("connectors", "schedule_enabled")
    op.drop_column("connectors", "cron_schedule")
    # Note: Cannot remove 'skipped' status from existing run_history rows
    # Downgrade will leave any skipped runs in the database
