"""add subject to message template

Revision ID: d2f4a6c8e9b1
Revises: b8f3e2d1c9a4
Create Date: 2026-05-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d2f4a6c8e9b1"
down_revision = "b8f3e2d1c9a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "message_template",
        sa.Column(
            "subject",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("message_template", "subject")
