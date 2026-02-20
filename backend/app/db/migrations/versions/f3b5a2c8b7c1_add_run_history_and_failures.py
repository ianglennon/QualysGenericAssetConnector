"""add_run_history_and_failures

Revision ID: f3b5a2c8b7c1
Revises: c3a7e5f82d16
Create Date: 2026-02-20 17:28:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3b5a2c8b7c1"
down_revision: Union[str, None] = "c3a7e5f82d16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "run_history",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("connector_id", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("running", "success", "partial_success", "failed", name="runstatus"),
            nullable=False,
            server_default="running",
        ),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("records_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_submitted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_type", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("error_context", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_run_history_connector_id"), "run_history", ["connector_id"], unique=False)

    op.create_table(
        "run_failures",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("record_identifier", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["run_history.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_run_failures_run_id"), "run_failures", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_run_failures_run_id"), table_name="run_failures")
    op.drop_table("run_failures")
    op.drop_index(op.f("ix_run_history_connector_id"), table_name="run_history")
    op.drop_table("run_history")
