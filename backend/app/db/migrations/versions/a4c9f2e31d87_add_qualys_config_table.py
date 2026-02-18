"""add_qualys_config_table

Revision ID: a4c9f2e31d87
Revises: 085dbc92552b
Create Date: 2026-02-18 23:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4c9f2e31d87'
down_revision: Union[str, None] = '085dbc92552b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'qualys_config',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('api_url', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('encrypted_password', sa.String(), nullable=True),
        sa.Column('encrypted_token', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('qualys_config')
