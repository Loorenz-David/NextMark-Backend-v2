"""Add item_type_counts to order, route_plan, and route_group.

Revision ID: r1t6y2u8i4o0
Revises: de054463773c
Create Date: 2026-04-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "r1t6y2u8i4o0"
down_revision = "de054463773c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "order",
        sa.Column("item_type_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "route_plan",
        sa.Column("item_type_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "route_group",
        sa.Column("item_type_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade():
    op.drop_column("route_group", "item_type_counts")
    op.drop_column("route_plan", "item_type_counts")
    op.drop_column("order", "item_type_counts")
