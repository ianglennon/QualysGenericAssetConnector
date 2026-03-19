"""config model migration - drop api_url and encrypted_token

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-19 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print("Deleting qualys_config rows with NULL connector_uuid...")
    op.execute("DELETE FROM qualys_config WHERE connector_uuid IS NULL")

    with op.batch_alter_table("qualys_config") as batch_op:
        batch_op.drop_column("api_url")
        batch_op.drop_column("encrypted_token")
        batch_op.alter_column("connector_uuid", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("qualys_config") as batch_op:
        batch_op.alter_column("connector_uuid", nullable=True)
        batch_op.add_column(sa.Column("encrypted_token", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("api_url", sa.String(), nullable=False, server_default=""))
