"""Add run_events table and fault_diagnosis column to connectors.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'run_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('stage', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['run_history.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_run_events_run_id', 'run_events', ['run_id'])

    op.add_column('connectors', sa.Column('fault_diagnosis', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('connectors', 'fault_diagnosis')
    op.drop_index('ix_run_events_run_id', table_name='run_events')
    op.drop_table('run_events')
