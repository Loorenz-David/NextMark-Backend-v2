"""Rename order.delivery_plan_id to route_plan_id.

Revision ID: n2q6w4e8r1t3
Revises: z1a5b9c3d7e2
Create Date: 2026-03-26 00:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "n2q6w4e8r1t3"
down_revision = "z1a5b9c3d7e2"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade():
    if _has_column("order", "delivery_plan_id") and not _has_column("order", "route_plan_id"):
        with op.batch_alter_table("order") as batch_op:
            batch_op.alter_column("delivery_plan_id", new_column_name="route_plan_id")


def downgrade():
    if _has_column("order", "route_plan_id") and not _has_column("order", "delivery_plan_id"):
        with op.batch_alter_table("order") as batch_op:
            batch_op.alter_column("route_plan_id", new_column_name="delivery_plan_id")