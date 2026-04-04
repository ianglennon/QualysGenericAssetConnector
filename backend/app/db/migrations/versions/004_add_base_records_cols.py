"""Add base_records_* columns to run_history

These columns were added to the ORM model in Phase 60 (base-anchored stats
and enrichment breakdown) but never migrated.

Revision ID: 004_add_base_records_cols
Revises: 003_add_missing_erl_cols
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_add_base_records_cols"
down_revision: Union[str, None] = "003_add_missing_erl_cols"
branch_labels = None
depends_on = None

_COLS = [
    "base_records_total",
    "base_records_enriched",
    "base_records_submitted",
    "base_records_failed",
    "base_records_full",
    "base_records_partial",
    "base_records_base_only",
]


def upgrade() -> None:
    for col in _COLS:
        op.add_column("run_history", sa.Column(col, sa.Integer(), nullable=True))


def downgrade() -> None:
    for col in reversed(_COLS):
        op.drop_column("run_history", col)
