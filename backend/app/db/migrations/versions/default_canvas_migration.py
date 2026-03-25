"""auto-create Default canvas for connectors with endpoints

Revision ID: f7a8b9c0d1e2
Revises: e5a613d04e25
Create Date: 2026-03-25 20:00:00.000000
"""
from typing import Sequence, Union
import uuid
from datetime import datetime

from alembic import op
from sqlalchemy import text

revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e5a613d04e25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Find connectors with endpoints but no canvases (D-13: skip empty connectors)
    connectors_with_eps = conn.execute(text("""
        SELECT DISTINCT c.id FROM connectors c
        JOIN connector_endpoints ce ON ce.connector_id = c.id
        WHERE c.id NOT IN (SELECT DISTINCT connector_id FROM canvases)
    """)).fetchall()

    now = datetime.utcnow().isoformat()

    for (connector_id,) in connectors_with_eps:
        canvas_id = str(uuid.uuid4())

        # D-11: Create Default canvas
        conn.execute(text("""
            INSERT INTO canvases (id, connector_id, name, is_enabled, created_at, updated_at)
            VALUES (:id, :cid, 'Default', 1, :now, :now)
        """), {"id": canvas_id, "cid": connector_id, "now": now})

        # Create canvas_endpoint references for each endpoint
        endpoints = conn.execute(text("""
            SELECT id FROM connector_endpoints WHERE connector_id = :cid
        """), {"cid": connector_id}).fetchall()

        for (ep_id,) in endpoints:
            ce_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO canvas_endpoints (id, canvas_id, endpoint_id, field_role, max_concurrency, tree_order, created_at, updated_at)
                VALUES (:id, :canvas_id, :ep_id, 'data', 5, 0, :now, :now)
            """), {"id": ce_id, "canvas_id": canvas_id, "ep_id": ep_id, "now": now})

        # Update field_mappings to reference the canvas (prevent orphaned mappings)
        conn.execute(text("""
            UPDATE field_mappings SET canvas_id = :canvas_id
            WHERE endpoint_id IN (SELECT id FROM connector_endpoints WHERE connector_id = :cid)
            AND (canvas_id IS NULL OR canvas_id = '')
        """), {"canvas_id": canvas_id, "cid": connector_id})


def downgrade() -> None:
    conn = op.get_bind()
    # Remove auto-created Default canvases (only those named 'Default')
    # This also cascade-deletes canvas_endpoints via FK
    conn.execute(text("""
        DELETE FROM canvases WHERE name = 'Default'
    """))
    # Reset field_mapping canvas_id references
    conn.execute(text("""
        UPDATE field_mappings SET canvas_id = NULL
        WHERE canvas_id NOT IN (SELECT id FROM canvases)
    """))
