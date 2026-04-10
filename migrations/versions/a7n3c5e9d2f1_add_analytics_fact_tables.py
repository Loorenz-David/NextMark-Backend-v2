"""Add analytics route snapshot and daily fact tables.

Revision ID: a7n3c5e9d2f1
Revises: z1a5b9c3d7e2
Create Date: 2026-03-25 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "a7n3c5e9d2f1"
down_revision = "z1a5b9c3d7e2"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table in inspector.get_table_names()


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table))


def upgrade():
    if not _has_table("analytics_route_metrics_snapshot"):
        op.create_table(
            "analytics_route_metrics_snapshot",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("route_solution_id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("expected_start_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("total_stops", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("on_time_stops", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("early_stops", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("late_stops", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("avg_delay_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_delay_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("on_time_rate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("delay_rate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_distance_meters", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_travel_time_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_service_time_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_orders", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("zone_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["route_solution_id"], ["route_solution.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("route_solution_id", name="uq_analytics_rms_route_solution_id"),
        )

    if _has_table("analytics_route_metrics_snapshot"):
        if not _has_index("analytics_route_metrics_snapshot", "ix_analytics_rms_team_created"):
            op.create_index(
                "ix_analytics_rms_team_created",
                "analytics_route_metrics_snapshot",
                ["team_id", "created_at"],
                unique=False,
            )
        if not _has_index("analytics_route_metrics_snapshot", "ix_analytics_rms_expected_start"):
            op.create_index(
                "ix_analytics_rms_expected_start",
                "analytics_route_metrics_snapshot",
                ["expected_start_time"],
                unique=False,
            )
        if not _has_index("analytics_route_metrics_snapshot", "ix_analytics_rms_zone_id"):
            op.create_index(
                "ix_analytics_rms_zone_id",
                "analytics_route_metrics_snapshot",
                ["zone_id"],
                unique=False,
            )

    if not _has_table("analytics_daily_fact"):
        op.create_table(
            "analytics_daily_fact",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("total_orders_created", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_orders_completed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_orders_failed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("scheduled_orders", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unscheduled_orders", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_rate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_routes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("routes_completed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("routes_active", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("avg_delay_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("late_routes_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("on_time_routes_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_distance_meters", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_travel_time_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("zone_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if _has_table("analytics_daily_fact"):
        if not _has_index("analytics_daily_fact", "uix_analytics_daily_global"):
            op.create_index(
                "uix_analytics_daily_global",
                "analytics_daily_fact",
                ["team_id", "date"],
                unique=True,
                postgresql_where=sa.text("zone_id IS NULL"),
            )
        if not _has_index("analytics_daily_fact", "uix_analytics_daily_zoned"):
            op.create_index(
                "uix_analytics_daily_zoned",
                "analytics_daily_fact",
                ["team_id", "date", "zone_id"],
                unique=True,
                postgresql_where=sa.text("zone_id IS NOT NULL"),
            )
        if not _has_index("analytics_daily_fact", "ix_analytics_daily_fact_team_date_zone"):
            op.create_index(
                "ix_analytics_daily_fact_team_date_zone",
                "analytics_daily_fact",
                ["team_id", "date", "zone_id"],
                unique=False,
            )


def downgrade():
    if _has_table("analytics_daily_fact"):
        if _has_index("analytics_daily_fact", "ix_analytics_daily_fact_team_date_zone"):
            op.drop_index("ix_analytics_daily_fact_team_date_zone", table_name="analytics_daily_fact")
        if _has_index("analytics_daily_fact", "uix_analytics_daily_zoned"):
            op.drop_index("uix_analytics_daily_zoned", table_name="analytics_daily_fact")
        if _has_index("analytics_daily_fact", "uix_analytics_daily_global"):
            op.drop_index("uix_analytics_daily_global", table_name="analytics_daily_fact")
        op.drop_table("analytics_daily_fact")

    if _has_table("analytics_route_metrics_snapshot"):
        if _has_index("analytics_route_metrics_snapshot", "ix_analytics_rms_zone_id"):
            op.drop_index("ix_analytics_rms_zone_id", table_name="analytics_route_metrics_snapshot")
        if _has_index("analytics_route_metrics_snapshot", "ix_analytics_rms_expected_start"):
            op.drop_index("ix_analytics_rms_expected_start", table_name="analytics_route_metrics_snapshot")
        if _has_index("analytics_route_metrics_snapshot", "ix_analytics_rms_team_created"):
            op.drop_index("ix_analytics_rms_team_created", table_name="analytics_route_metrics_snapshot")
        op.drop_table("analytics_route_metrics_snapshot")
