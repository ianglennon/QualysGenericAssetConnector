"""Add base_canvas_endpoint_id column to canvases table.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("canvases") as batch_op:
        batch_op.add_column(
            sa.Column("base_canvas_endpoint_id", sa.String(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_canvases_base_endpoint",
            "canvas_endpoints",
            ["base_canvas_endpoint_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("canvases") as batch_op:
        batch_op.drop_constraint("fk_canvases_base_endpoint", type_="foreignkey")
        batch_op.drop_column("base_canvas_endpoint_id")
