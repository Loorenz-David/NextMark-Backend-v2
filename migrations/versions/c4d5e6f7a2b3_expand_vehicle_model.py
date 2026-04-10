"""expand vehicle model with facility FK, status, capabilities, and cost columns

Revision ID: c4d5e6f7a2b3
Revises: b3c4d5e6f7a2
Create Date: 2026-03-29 12:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c4d5e6f7a2b3"
down_revision = "b3c4d5e6f7a2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "vehicle",
        sa.Column(
            "home_facility_id",
            sa.Integer(),
            sa.ForeignKey("facility.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "vehicle",
        sa.Column("status", sa.String(), nullable=False, server_default="idle"),
    )
    op.add_column(
        "vehicle",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "vehicle",
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "vehicle",
        sa.Column(
            "loading_time_per_stop_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "vehicle",
        sa.Column(
            "unloading_time_per_stop_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "vehicle",
        sa.Column("fixed_cost", sa.Float(), nullable=False, server_default="0"),
    )

    op.create_index("ix_vehicle_home_facility_id", "vehicle", ["team_id", "home_facility_id"])
    op.create_index("ix_vehicle_is_active", "vehicle", ["team_id", "is_active"])
    op.create_index("ix_vehicle_status", "vehicle", ["team_id", "status"])


def downgrade():
    op.drop_index("ix_vehicle_status", table_name="vehicle")
    op.drop_index("ix_vehicle_is_active", table_name="vehicle")
    op.drop_index("ix_vehicle_home_facility_id", table_name="vehicle")
    op.drop_column("vehicle", "fixed_cost")
    op.drop_column("vehicle", "unloading_time_per_stop_seconds")
    op.drop_column("vehicle", "loading_time_per_stop_seconds")
    op.drop_column("vehicle", "capabilities")
    op.drop_column("vehicle", "is_active")
    op.drop_column("vehicle", "status")
    op.drop_column("vehicle", "home_facility_id")
