"""Add canvas_endpoint_id to endpoint_run_logs"""
from typing import Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column('endpoint_run_logs',
        sa.Column('canvas_endpoint_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('endpoint_run_logs', 'canvas_endpoint_id')
