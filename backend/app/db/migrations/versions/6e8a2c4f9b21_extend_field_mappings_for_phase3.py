"""extend_field_mappings_for_phase3

Revision ID: 6e8a2c4f9b21
Revises: f3b5a2c8b7c1
Create Date: 2026-02-20 17:34:45.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6e8a2c4f9b21"
down_revision: Union[str, None] = "f3b5a2c8b7c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("field_mappings", sa.Column("target_field", sa.String(), nullable=True))
    op.add_column("field_mappings", sa.Column("mapping_type", sa.String(), nullable=True))
    op.add_column("field_mappings", sa.Column("source_field", sa.String(), nullable=True))
    op.add_column("field_mappings", sa.Column("static_value", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("field_mappings", "static_value")
    op.drop_column("field_mappings", "source_field")
    op.drop_column("field_mappings", "mapping_type")
    op.drop_column("field_mappings", "target_field")
