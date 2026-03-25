"""add depth and source_api_calls columns to endpoint_run_logs

Revision ID: e5a613d04e25
Revises: d49b02c03d14
Create Date: 2026-03-25 16:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a613d04e25'
down_revision: Union[str, None] = 'd49b02c03d14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists (handles create_all + Alembic overlap in tests)."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        if not _column_exists("endpoint_run_logs", "depth"):
            batch_op.add_column(sa.Column("depth", sa.Integer(), nullable=True))
        if not _column_exists("endpoint_run_logs", "source_api_calls"):
            batch_op.add_column(sa.Column("source_api_calls", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        batch_op.drop_column("source_api_calls")
        batch_op.drop_column("depth")
