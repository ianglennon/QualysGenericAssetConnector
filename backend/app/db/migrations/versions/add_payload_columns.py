"""add payload capture columns to endpoint_run_logs

Revision ID: a1b2c3d4e5f6
Revises: 75cdda35b369
Create Date: 2026-03-18 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '75cdda35b369'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        batch_op.add_column(sa.Column("failure_stage", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("http_request", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("http_response", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("endpoint_run_logs") as batch_op:
        batch_op.drop_column("http_response")
        batch_op.drop_column("http_request")
        batch_op.drop_column("failure_stage")
