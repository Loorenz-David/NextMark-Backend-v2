"""Add tracking token fields to order table.

Revision ID: q5r1s8t3u7v2
Revises: p4r8s2t6u1v5
Create Date: 2025-01-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "q5r1s8t3u7v2"
down_revision = "p4r8s2t6u1v5"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    if "order" not in existing_tables:
        return

    columns = [col["name"] for col in inspector.get_columns("order")]

    if "tracking_token_hash" not in columns:
        op.add_column(
            "order",
            sa.Column("tracking_token_hash", sa.String(64), nullable=True),
        )
        op.create_unique_constraint(
            "uq_order_tracking_token_hash",
            "order",
            ["tracking_token_hash"],
        )
        op.create_index(
            "ix_order_tracking_token_hash",
            "order",
            ["tracking_token_hash"],
        )

    if "tracking_token_created_at" not in columns:
        op.add_column(
            "order",
            sa.Column("tracking_token_created_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade():
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    if "order" not in existing_tables:
        return

    columns = [col["name"] for col in inspector.get_columns("order")]

    if "tracking_token_created_at" in columns:
        op.drop_column("order", "tracking_token_created_at")

    if "tracking_token_hash" in columns:
        op.drop_index("ix_order_tracking_token_hash", table_name="order")
        op.drop_constraint("uq_order_tracking_token_hash", "order", type_="unique")
        op.drop_column("order", "tracking_token_hash")
