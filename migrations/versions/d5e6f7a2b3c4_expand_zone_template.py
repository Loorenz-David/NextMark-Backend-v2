"""expand zone_template: replace config_json with typed operational columns

Revision ID: d5e6f7a2b3c4
Revises: c4d5e6f7a2b3
Create Date: 2026-03-29 12:15:00.000000

NOTE: config_json is dropped in this migration. Before running in production,
verify that all existing rows have empty config_json ({}) by running:
    SELECT COUNT(*) FROM zone_template WHERE config_json != '{}';
If any rows have non-empty config_json, write a data migration loop first.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d5e6f7a2b3c4"
down_revision = "c4d5e6f7a2b3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "zone_template",
        sa.Column(
            "default_facility_id",
            sa.Integer(),
            sa.ForeignKey("facility.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "zone_template",
        sa.Column("max_orders_per_route", sa.Integer(), nullable=True),
    )
    op.add_column(
        "zone_template",
        sa.Column("max_vehicles", sa.Integer(), nullable=True),
    )
    op.add_column(
        "zone_template",
        sa.Column("operating_window_start", sa.String(5), nullable=True),
    )
    op.add_column(
        "zone_template",
        sa.Column("operating_window_end", sa.String(5), nullable=True),
    )
    op.add_column(
        "zone_template",
        sa.Column(
            "eta_tolerance_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "zone_template",
        sa.Column(
            "vehicle_capabilities_required",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "zone_template",
        sa.Column(
            "preferred_vehicle_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "zone_template",
        sa.Column(
            "default_route_end_strategy",
            sa.String(),
            nullable=False,
            server_default="round_trip",
        ),
    )
    op.add_column(
        "zone_template",
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_zone_template_default_facility",
        "zone_template",
        ["team_id", "default_facility_id"],
    )

    # config_json defaults to {} and has no live data — drop immediately
    op.drop_column("zone_template", "config_json")


def downgrade():
    op.add_column(
        "zone_template",
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.drop_index("ix_zone_template_default_facility", table_name="zone_template")
    op.drop_column("zone_template", "meta")
    op.drop_column("zone_template", "default_route_end_strategy")
    op.drop_column("zone_template", "preferred_vehicle_ids")
    op.drop_column("zone_template", "vehicle_capabilities_required")
    op.drop_column("zone_template", "eta_tolerance_seconds")
    op.drop_column("zone_template", "operating_window_end")
    op.drop_column("zone_template", "operating_window_start")
    op.drop_column("zone_template", "max_vehicles")
    op.drop_column("zone_template", "max_orders_per_route")
    op.drop_column("zone_template", "default_facility_id")
