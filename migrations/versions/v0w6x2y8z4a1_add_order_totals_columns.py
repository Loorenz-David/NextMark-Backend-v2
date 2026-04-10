"""Add total_weight_g, total_volume_cm3, total_item_count columns to order table.

Revision ID: v0w6x2y8z4a1
Revises: u9v5w1x7y3z0
Create Date: 2025-01-04 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = "v0w6x2y8z4a1"
down_revision = "u9v5w1x7y3z0"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade():
    if not _has_column("order", "total_weight_g"):
        op.add_column(
            "order",
            sa.Column("total_weight_g", sa.Float(), nullable=True),
        )
    if not _has_column("order", "total_volume_cm3"):
        op.add_column(
            "order",
            sa.Column("total_volume_cm3", sa.Float(), nullable=True),
        )
    if not _has_column("order", "total_item_count"):
        op.add_column(
            "order",
            sa.Column("total_item_count", sa.Integer(), nullable=True),
        )

    # Backfill existing orders by aggregating from the item table.
    # Uses raw SQL so no ORM models are needed at migration time.
    # Safe to re-run — only updates rows where the columns are still NULL.
    op.get_bind().execute(text("""
        UPDATE "order" o
        SET
            total_weight_g    = COALESCE(agg.total_weight_g,    0),
            total_volume_cm3  = COALESCE(agg.total_volume_cm3,  0),
            total_item_count  = COALESCE(agg.total_item_count,  0)
        FROM (
            SELECT
                i.order_id,
                SUM(COALESCE(i.weight, 0) * COALESCE(i.quantity, 1))
                    AS total_weight_g,
                SUM(
                    COALESCE(i.dimension_depth,  0) *
                    COALESCE(i.dimension_height, 0) *
                    COALESCE(i.dimension_width,  0) *
                    COALESCE(i.quantity, 1)
                )   AS total_volume_cm3,
                SUM(COALESCE(i.quantity, 1))
                    AS total_item_count
            FROM item i
            GROUP BY i.order_id
        ) agg
        WHERE o.id = agg.order_id
          AND o.total_weight_g IS NULL
    """))

    # Orders with no items at all get explicit zeros instead of NULL.
    op.get_bind().execute(text("""
        UPDATE "order"
        SET
            total_weight_g   = 0,
            total_volume_cm3 = 0,
            total_item_count = 0
        WHERE total_weight_g IS NULL
    """))


def downgrade():
    if _has_column("order", "total_item_count"):
        op.drop_column("order", "total_item_count")
    if _has_column("order", "total_volume_cm3"):
        op.drop_column("order", "total_volume_cm3")
    if _has_column("order", "total_weight_g"):
        op.drop_column("order", "total_weight_g")
