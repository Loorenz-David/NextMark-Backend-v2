"""add start_facility_id and end_facility_id to route_solution

Revision ID: e6f7a2b3c4d5
Revises: d5e6f7a2b3c4
Create Date: 2026-03-29 12:20:00.000000

Resolution rule (enforced in domain layer, not here):
  - When start_facility_id is set → optimizer uses facility.property_location.coordinates
    as the route start anchor; start_location JSONB is ignored.
  - When start_facility_id is null → optimizer falls back to start_location JSONB.
"""

from alembic import op
import sqlalchemy as sa

revision = "e6f7a2b3c4d5"
down_revision = "d5e6f7a2b3c4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "route_solution",
        sa.Column(
            "start_facility_id",
            sa.Integer(),
            sa.ForeignKey("facility.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "route_solution",
        sa.Column(
            "end_facility_id",
            sa.Integer(),
            sa.ForeignKey("facility.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_route_solution_start_facility_id",
        "route_solution",
        ["start_facility_id"],
    )


def downgrade():
    op.drop_index("ix_route_solution_start_facility_id", table_name="route_solution")
    op.drop_column("route_solution", "end_facility_id")
    op.drop_column("route_solution", "start_facility_id")
