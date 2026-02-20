"""extend field mappings for conditional rules

Revision ID: 21b188e0e180
Revises: d8e4a1b9c2f3
Create Date: 2026-02-20 22:12:12.748901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21b188e0e180'
down_revision: Union[str, None] = 'd8e4a1b9c2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add conditional mapping support to field_mappings and validation flag to connectors
    op.add_column('connectors', sa.Column('is_valid_mappings', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('field_mappings', sa.Column('conditions', sa.JSON(), nullable=True))
    op.add_column('field_mappings', sa.Column('fallback', sa.String(), nullable=True))
    op.add_column('field_mappings', sa.Column('order', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    # Remove conditional mapping columns
    op.drop_column('field_mappings', 'order')
    op.drop_column('field_mappings', 'fallback')
    op.drop_column('field_mappings', 'conditions')
    op.drop_column('connectors', 'is_valid_mappings')
