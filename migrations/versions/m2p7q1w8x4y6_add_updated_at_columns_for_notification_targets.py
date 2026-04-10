"""add updated_at columns for notification targets

Revision ID: m2p7q1w8x4y6
Revises: k3n9p5q8r2s6, f91a6e8c2d4b, 9c1f7d2ab4e3, b2e4d9f6c1aa
Create Date: 2026-03-18 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

from Delivery_app_BK.models.utils import UTCDateTime


revision = "m2p7q1w8x4y6"
down_revision = ("k3n9p5q8r2s6", "f91a6e8c2d4b", "9c1f7d2ab4e3", "b2e4d9f6c1aa")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order", sa.Column("updated_at", UTCDateTime(), nullable=True))
    op.add_column("order_case", sa.Column("updated_at", UTCDateTime(), nullable=True))
    op.add_column("delivery_plan", sa.Column("updated_at", UTCDateTime(), nullable=True))
    op.add_column("local_delivery_plan", sa.Column("updated_at", UTCDateTime(), nullable=True))
    op.add_column("route_solution", sa.Column("updated_at", UTCDateTime(), nullable=True))
    op.add_column("route_solution_stop", sa.Column("updated_at", UTCDateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("route_solution_stop", "updated_at")
    op.drop_column("route_solution", "updated_at")
    op.drop_column("local_delivery_plan", "updated_at")
    op.drop_column("delivery_plan", "updated_at")
    op.drop_column("order_case", "updated_at")
    op.drop_column("order", "updated_at")
