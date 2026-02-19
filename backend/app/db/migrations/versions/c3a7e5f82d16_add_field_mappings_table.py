"""add_field_mappings_table

Revision ID: c3a7e5f82d16
Revises: b2f8c4d91e05
Create Date: 2026-02-19 12:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a7e5f82d16'
down_revision: Union[str, None] = 'b2f8c4d91e05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Minimal shell table — full schema added in Phase 5.
    # Only id, connector_id FK, and created_at are needed here so that
    # ON DELETE CASCADE can be exercised once the connector CRUD router exists.
    op.create_table(
        'field_mappings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('connector_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['connector_id'], ['connectors.id'],
            ondelete='CASCADE',
        ),
    )


def downgrade() -> None:
    op.drop_table('field_mappings')
