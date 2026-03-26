"""Add data_root column to connector_endpoints and collect mapping columns to field_mappings.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-26 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: str = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add data_root to connector_endpoints
    with op.batch_alter_table("connector_endpoints") as batch_op:
        batch_op.add_column(sa.Column("data_root", sa.String(), nullable=True))

    # Add collect mapping columns to field_mappings
    with op.batch_alter_table("field_mappings") as batch_op:
        batch_op.add_column(sa.Column("array_path", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("extract_field", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("collect_filter", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("separator", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("field_mappings") as batch_op:
        batch_op.drop_column("separator")
        batch_op.drop_column("collect_filter")
        batch_op.drop_column("extract_field")
        batch_op.drop_column("array_path")

    with op.batch_alter_table("connector_endpoints") as batch_op:
        batch_op.drop_column("data_root")
