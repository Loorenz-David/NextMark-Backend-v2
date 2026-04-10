"""Add user_name column to case_chat.

Revision ID: j2m8q4v1c7k5
Revises: h1j4k7m2n9p0
Create Date: 2026-03-18 15:15:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "j2m8q4v1c7k5"
down_revision = "h1j4k7m2n9p0"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    if "case_chat" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("case_chat")]
        if "user_name" not in columns:
            op.add_column("case_chat", sa.Column("user_name", sa.String(), nullable=True))


def downgrade():
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    if "case_chat" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("case_chat")]
        if "user_name" in columns:
            op.drop_column("case_chat", "user_name")
