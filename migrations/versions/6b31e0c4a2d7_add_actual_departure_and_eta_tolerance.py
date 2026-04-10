"""add actual departure and eta tolerance to route solutions

Revision ID: 6b31e0c4a2d7
Revises: aa3d4c9f1b21
Create Date: 2026-03-10 16:10:00.000000
"""

from alembic import op
import sqlalchemy as sa

from Delivery_app_BK.models.utils import UTCDateTime


revision = "6b31e0c4a2d7"
down_revision = "aa3d4c9f1b21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "route_solution",
        sa.Column("eta_tolerance_seconds", sa.Integer(), nullable=True, server_default=sa.text("0")),
    )
    op.execute(
        """
        UPDATE route_solution
        SET eta_tolerance_seconds = 0
        WHERE eta_tolerance_seconds IS NULL
        """
    )
    with op.batch_alter_table("route_solution", schema=None) as batch_op:
        batch_op.alter_column("eta_tolerance_seconds", nullable=False, existing_type=sa.Integer())
        batch_op.alter_column("eta_tolerance_seconds", server_default=None, existing_type=sa.Integer())

    op.add_column(
        "route_solution_stop",
        sa.Column("actual_departure_time", UTCDateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("route_solution_stop", "actual_departure_time")
    op.drop_column("route_solution", "eta_tolerance_seconds")
