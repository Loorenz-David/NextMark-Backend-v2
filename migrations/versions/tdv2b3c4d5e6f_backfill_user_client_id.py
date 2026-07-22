"""backfill user.client_id for rows missing it

Idempotent: only rows with NULL or empty client_id are updated. Safe to
re-run. Kept separate from the DDL migration so it can be reviewed and
replayed independently. Uses the same ``user_<uuid4hex>`` shape that
``generate_client_id("user")`` produces.

Revision ID: tdv2b3c4d5e6f
Revises: tdv1a2b3c4d5
Create Date: 2026-07-21 00:00:00.000000
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "tdv2b3c4d5e6f"
down_revision = "tdv1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id FROM \"user\" "
            "WHERE client_id IS NULL OR client_id = ''"
        )
    ).fetchall()
    for (user_id,) in rows:
        conn.execute(
            sa.text('UPDATE "user" SET client_id = :cid WHERE id = :uid'),
            {"cid": f"user_{uuid4().hex}", "uid": user_id},
        )


def downgrade() -> None:
    # Backfilled identifiers are stable and referenced by clients; do not
    # remove them on downgrade.
    pass
