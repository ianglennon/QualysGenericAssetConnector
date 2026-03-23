"""create canvases and canvas_endpoints tables, alter existing tables

Revision ID: c38a01b02c03
Revises: b2c3d4e5f6a7
Create Date: 2026-03-23 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c38a01b02c03'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create canvases table
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

    # 2. Create canvas_endpoints table
    op.create_table(
        'canvas_endpoints',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('canvas_id', sa.String(), nullable=False),
        sa.Column('endpoint_id', sa.String(), nullable=False),
        sa.Column('parent_ref_id', sa.String(), nullable=True),
        sa.Column('field_role', sa.String(), nullable=False, server_default='data'),
        sa.Column('variable_extractions', sa.JSON(), nullable=True),
        sa.Column('max_concurrency', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('tree_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['canvas_id'], ['canvases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['endpoint_id'], ['connector_endpoints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_ref_id'], ['canvas_endpoints.id'], ondelete='SET NULL'),
    )

    # 3. Create indexes
    op.create_index('ix_canvas_endpoints_canvas_id', 'canvas_endpoints', ['canvas_id'])
    op.create_index('ix_canvas_endpoints_endpoint_id', 'canvas_endpoints', ['endpoint_id'])

    # 4. Alter existing tables
    with op.batch_alter_table("field_mappings") as batch_op:
        batch_op.add_column(sa.Column("canvas_id", sa.String(), nullable=True))
        batch_op.alter_column("endpoint_id", nullable=True)
        batch_op.create_foreign_key(
            "fk_field_mappings_canvas_id", "canvases", ["canvas_id"], ["id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("run_history") as batch_op:
        batch_op.add_column(sa.Column("source_api_calls", sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column("qualys_api_calls", sa.Integer(), nullable=True, server_default='0'))

    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        batch_op.add_column(sa.Column("canvas_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("source_api_calls", sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    # Reverse alterations to existing tables
    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        batch_op.drop_column("source_api_calls")
        batch_op.drop_column("canvas_id")

    with op.batch_alter_table("run_history") as batch_op:
        batch_op.drop_column("qualys_api_calls")
        batch_op.drop_column("source_api_calls")

    with op.batch_alter_table("field_mappings") as batch_op:
        batch_op.drop_constraint("fk_field_mappings_canvas_id", type_="foreignkey")
        batch_op.alter_column("endpoint_id", nullable=False)
        batch_op.drop_column("canvas_id")

    # Drop indexes
    op.drop_index('ix_canvas_endpoints_endpoint_id', table_name='canvas_endpoints')
    op.drop_index('ix_canvas_endpoints_canvas_id', table_name='canvas_endpoints')

    # Drop tables in reverse order (canvas_endpoints depends on canvases)
    op.drop_table('canvas_endpoints')
    op.drop_table('canvases')
