"""add actual end time to route solution

Revision ID: 91d3a0e52b6f
Revises: 4c7e9b1a2d44
Create Date: 2026-03-10 21:05:00.000000
"""

from alembic import op
import sqlalchemy as sa

from Delivery_app_BK.models.utils import UTCDateTime


revision = "91d3a0e52b6f"
down_revision = "4c7e9b1a2d44"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "route_solution",
        sa.Column("actual_end_time", UTCDateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("route_solution", "actual_end_time")
