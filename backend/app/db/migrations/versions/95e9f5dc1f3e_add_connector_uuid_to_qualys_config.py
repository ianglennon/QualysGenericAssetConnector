"""add_connector_uuid_to_qualys_config

Revision ID: 95e9f5dc1f3e
Revises: 9a3b7c4d2f1e
Create Date: 2026-02-20 19:20:05.114157

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95e9f5dc1f3e'
down_revision: Union[str, None] = '9a3b7c4d2f1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add connector_uuid column to qualys_config table
    op.add_column('qualys_config', sa.Column('connector_uuid', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove connector_uuid column from qualys_config table
    op.drop_column('qualys_config', 'connector_uuid')
