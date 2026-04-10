"""Add order_notes JSONB column to order table.

Revision ID: s7t3u9v5w1x8
Revises: r6s2t9u4v8w3
Create Date: 2025-01-02 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "s7t3u9v5w1x8"
down_revision = "r6s2t9u4v8w3"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade():
    if not _has_column("order", "order_notes"):
        op.add_column(
            "order",
            sa.Column("order_notes", postgresql.JSONB(), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("order")}
    if "order_notes" in columns:
        op.drop_column("order", "order_notes")
