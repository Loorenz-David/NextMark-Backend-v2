"""add actual end time source to route solution

Revision ID: f2c4e8d91ab7
Revises: 91d3a0e52b6f
Create Date: 2026-03-12 21:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f2c4e8d91ab7"
down_revision = "91d3a0e52b6f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "route_solution",
        sa.Column("actual_end_time_source", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_column("route_solution", "actual_end_time_source")
