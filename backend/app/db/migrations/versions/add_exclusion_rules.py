"""Add canvases, canvas_endpoints (with exclusion_rules), and records_filtered to endpoint_run_logs

Revision ID: a1b2c3d4e5f7
Revises: b2c3d4e5f6a7
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create canvases table (FK target for canvas_endpoints)
    op.create_table(
        'canvases',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('connector_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_enabled', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['connector_id'], ['connectors.id'], ondelete='CASCADE'),
    )

    # Create canvas_endpoints table with exclusion_rules JSON column
    op.create_table(
        'canvas_endpoints',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('canvas_id', sa.String(), nullable=False),
        sa.Column('endpoint_id', sa.String(), nullable=False),
        sa.Column('parent_ref_id', sa.String(), nullable=True),
        sa.Column('field_role', sa.String(), nullable=False, server_default='data'),
        sa.Column('variable_extractions', sa.JSON(), nullable=True),
        sa.Column('max_concurrency', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('exclusion_rules', sa.JSON(), nullable=True),
        sa.Column('tree_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['canvas_id'], ['canvases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['endpoint_id'], ['connector_endpoints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_ref_id'], ['canvas_endpoints.id'], ondelete='SET NULL'),
    )

    # Add records_filtered to endpoint_run_logs
    op.add_column('endpoint_run_logs', sa.Column('records_filtered', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('endpoint_run_logs', 'records_filtered')
    op.drop_table('canvas_endpoints')
    op.drop_table('canvases')
