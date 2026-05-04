"""Add item_images to item table.

Revision ID: b8f3e2d1c9a4
Revises: u6v2w8x4y1z7
Create Date: 2026-05-04 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b8f3e2d1c9a4"
down_revision = "u6v2w8x4y1z7"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade():
    if not _has_column("item", "item_images"):
        op.add_column(
            "item",
            sa.Column(
                "item_images",
                postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
                nullable=True,
            ),
        )


def downgrade():
    if _has_column("item", "item_images"):
        op.drop_column("item", "item_images")
