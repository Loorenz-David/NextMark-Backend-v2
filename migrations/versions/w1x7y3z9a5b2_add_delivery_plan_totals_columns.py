"""Add total_weight_g, total_volume_cm3, total_item_count, total_orders to delivery_plan.

Revision ID: w1x7y3z9a5b2
Revises: v0w6x2y8z4a1
Create Date: 2025-01-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = "w1x7y3z9a5b2"
down_revision = "v0w6x2y8z4a1"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade():
    if not _has_column("delivery_plan", "total_weight_g"):
        op.add_column("delivery_plan", sa.Column("total_weight_g", sa.Float(), nullable=True))
    if not _has_column("delivery_plan", "total_volume_cm3"):
        op.add_column("delivery_plan", sa.Column("total_volume_cm3", sa.Float(), nullable=True))
    if not _has_column("delivery_plan", "total_item_count"):
        op.add_column("delivery_plan", sa.Column("total_item_count", sa.Integer(), nullable=True))
    if not _has_column("delivery_plan", "total_orders"):
        op.add_column("delivery_plan", sa.Column("total_orders", sa.Integer(), nullable=True))

    # Backfill from denormalized order totals (no items join needed — order-level
    # total_weight_g / total_volume_cm3 / total_item_count were populated by the
    # previous migration v0w6x2y8z4a1).
    op.get_bind().execute(text("""
        UPDATE delivery_plan dp
        SET
            total_weight_g   = COALESCE(agg.w, 0),
            total_volume_cm3 = COALESCE(agg.v, 0),
            total_item_count = COALESCE(agg.i, 0),
            total_orders     = COALESCE(agg.c, 0)
        FROM (
            SELECT delivery_plan_id,
                   SUM(total_weight_g)   AS w,
                   SUM(total_volume_cm3) AS v,
                   SUM(total_item_count) AS i,
                   COUNT(*)              AS c
            FROM "order"
            WHERE delivery_plan_id IS NOT NULL
            GROUP BY delivery_plan_id
        ) agg
        WHERE dp.id = agg.delivery_plan_id
          AND dp.total_orders IS NULL
    """))

    # Plans with no orders (or no matching orders) get explicit zeros.
    op.get_bind().execute(text("""
        UPDATE delivery_plan
        SET total_weight_g   = 0,
            total_volume_cm3 = 0,
            total_item_count = 0,
            total_orders     = 0
        WHERE total_orders IS NULL
    """))


def downgrade():
    for col in ["total_orders", "total_item_count", "total_volume_cm3", "total_weight_g"]:
        if _has_column("delivery_plan", col):
            op.drop_column("delivery_plan", col)
