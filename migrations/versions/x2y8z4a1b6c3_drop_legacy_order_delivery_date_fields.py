"""drop_legacy_order_delivery_date_fields

Revision ID: x2y8z4a1b6c3
Revises: w1x7y3z9a5b2
Create Date: 2025-01-06 00:00:00.000000

Drops the four legacy delivery scheduling hint columns from the order table.
These were superseded by the OrderDeliveryWindow model (delivery_windows relationship).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "x2y8z4a1b6c3"
down_revision = "w1x7y3z9a5b2"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("order", "earliest_delivery_date")
    op.drop_column("order", "latest_delivery_date")
    op.drop_column("order", "preferred_time_start")
    op.drop_column("order", "preferred_time_end")


def downgrade():
    op.add_column(
        "order",
        sa.Column("preferred_time_end", sa.String(), nullable=True),
    )
    op.add_column(
        "order",
        sa.Column("preferred_time_start", sa.String(), nullable=True),
    )
    op.add_column(
        "order",
        sa.Column(
            "latest_delivery_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "order",
        sa.Column(
            "earliest_delivery_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_order_earliest_delivery_date",
        "order",
        ["earliest_delivery_date"],
        unique=False,
    )
    op.create_index(
        "ix_order_latest_delivery_date",
        "order",
        ["latest_delivery_date"],
        unique=False,
    )
