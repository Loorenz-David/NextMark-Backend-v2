"""add encrypted client form token storage

Revision ID: c6d4e1f8a2b9
Revises: k3n9p5q8r2s6
Create Date: 2026-04-04 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "c6d4e1f8a2b9"
down_revision = "k3n9p5q8r2s6"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    if "order" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("order")]
        if "client_form_token_encrypted" not in columns:
            op.add_column(
                "order",
                sa.Column("client_form_token_encrypted", sa.String(), nullable=True),
            )


def downgrade():
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    if "order" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("order")]
        if "client_form_token_encrypted" in columns:
            op.drop_column("order", "client_form_token_encrypted")
