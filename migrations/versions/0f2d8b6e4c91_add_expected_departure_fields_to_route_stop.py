"""add expected departure fields to route stop

Revision ID: 0f2d8b6e4c91
Revises: 6b31e0c4a2d7
Create Date: 2026-03-10 12:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0f2d8b6e4c91"
down_revision = "6b31e0c4a2d7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "route_solution_stop",
        sa.Column("expected_service_duration_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "route_solution_stop",
        sa.Column("expected_departure_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_route_solution_stop_route_solution_id_stop_order",
        "route_solution_stop",
        ["route_solution_id", "stop_order"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_route_solution_stop_route_solution_id_stop_order",
        table_name="route_solution_stop",
    )
    op.drop_column("route_solution_stop", "expected_departure_time")
    op.drop_column("route_solution_stop", "expected_service_duration_seconds")
