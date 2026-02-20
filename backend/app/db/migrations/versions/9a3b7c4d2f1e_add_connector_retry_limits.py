"""add_connector_retry_limits

Revision ID: 9a3b7c4d2f1e
Revises: 6e8a2c4f9b21
Create Date: 2026-02-20 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9a3b7c4d2f1e"
down_revision: Union[str, None] = "6e8a2c4f9b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("connectors", sa.Column("source_retry_limit", sa.Integer(), nullable=True))
    op.add_column("connectors", sa.Column("qualys_retry_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("connectors", "qualys_retry_limit")
    op.drop_column("connectors", "source_retry_limit")
