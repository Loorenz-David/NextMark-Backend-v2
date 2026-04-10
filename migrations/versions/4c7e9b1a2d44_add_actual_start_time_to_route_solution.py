"""add actual start time to route solution

Revision ID: 4c7e9b1a2d44
Revises: 0f2d8b6e4c91
Create Date: 2026-03-10 19:15:00.000000
"""

from alembic import op
import sqlalchemy as sa

from Delivery_app_BK.models.utils import UTCDateTime


revision = "4c7e9b1a2d44"
down_revision = "0f2d8b6e4c91"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "route_solution",
        sa.Column("actual_start_time", UTCDateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("route_solution", "actual_start_time")
