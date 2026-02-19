"""add_connectors_table

Revision ID: b2f8c4d91e05
Revises: a4c9f2e31d87
Create Date: 2026-02-19 12:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f8c4d91e05'
down_revision: Union[str, None] = 'a4c9f2e31d87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'connectors',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('base_url', sa.String(), nullable=False),
        sa.Column('test_path', sa.String(), nullable=True),
        sa.Column('auth_method', sa.String(), nullable=False),
        sa.Column('encrypted_token', sa.String(), nullable=True),
        sa.Column('encrypted_username', sa.String(), nullable=True),
        sa.Column('encrypted_password', sa.String(), nullable=True),
        sa.Column('api_key_name', sa.String(), nullable=True),
        sa.Column('encrypted_api_key', sa.String(), nullable=True),
        sa.Column('pagination_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('connectors')
