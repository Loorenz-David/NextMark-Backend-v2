"""Add client form token fields to order table.

Revision ID: k3n9p5q8r2s6
Revises: j2m8q4v1c7k5
Create Date: 2025-01-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "k3n9p5q8r2s6"
down_revision = "j2m8q4v1c7k5"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    if "order" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("order")]

        if "client_form_token_hash" not in columns:
            op.add_column(
                "order",
                sa.Column("client_form_token_hash", sa.String(64), nullable=True),
            )
            op.create_unique_constraint(
                "uq_order_client_form_token_hash",
                "order",
                ["client_form_token_hash"],
            )
            op.create_index(
                "ix_order_client_form_token_hash",
                "order",
                ["client_form_token_hash"],
            )

        if "client_form_token_expires_at" not in columns:
            op.add_column(
                "order",
                sa.Column("client_form_token_expires_at", sa.DateTime(timezone=True), nullable=True),
            )

        if "client_form_submitted_at" not in columns:
            op.add_column(
                "order",
                sa.Column("client_form_submitted_at", sa.DateTime(timezone=True), nullable=True),
            )


def downgrade():
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    if "order" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("order")]

        if "client_form_submitted_at" in columns:
            op.drop_column("order", "client_form_submitted_at")

        if "client_form_token_expires_at" in columns:
            op.drop_column("order", "client_form_token_expires_at")

        if "client_form_token_hash" in columns:
            # Drop index and unique constraint before the column
            op.drop_index("ix_order_client_form_token_hash", table_name="order")
            op.drop_constraint(
                "uq_order_client_form_token_hash", "order", type_="unique"
            )
            op.drop_column("order", "client_form_token_hash")
