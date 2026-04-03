"""Add base-anchored record columns and endpoint role.

Per Phase 60 D-01, D-03: submission statistics and enrichment counters.

Revision ID: d6e7f8a9b0c1
Revises: g8b9c0d1e2f3
Create Date: 2026-04-03 11:46:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, None] = 'g8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists (handles create_all + Alembic overlap in tests)."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    with op.batch_alter_table("run_history") as batch_op:
        for col_name in [
            "base_records_total", "base_records_enriched",
            "base_records_submitted", "base_records_failed",
            "base_records_full", "base_records_partial", "base_records_base_only",
        ]:
            if not _column_exists("run_history", col_name):
                batch_op.add_column(sa.Column(col_name, sa.Integer(), nullable=True))

    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        if not _column_exists("endpoint_run_logs", "endpoint_role"):
            batch_op.add_column(sa.Column("endpoint_role", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run_history") as batch_op:
        for col_name in [
            "base_records_total", "base_records_enriched",
            "base_records_submitted", "base_records_failed",
            "base_records_full", "base_records_partial", "base_records_base_only",
        ]:
            batch_op.drop_column(col_name)
    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        batch_op.drop_column("endpoint_role")
