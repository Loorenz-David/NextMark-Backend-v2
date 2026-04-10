"""Add versioned cross-domain zone foundation.

Revision ID: b3c4d5e6f7a8
Revises: a7n3c5e9d2f1
Create Date: 2026-03-25 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "a7n3c5e9d2f1"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table in inspector.get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(col.get("name") == column for col in inspector.get_columns(table))


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table))


zone_type_enum = sa.Enum("bootstrap", "system", "user", name="zone_type_enum")
zone_assignment_type_enum = sa.Enum("auto", "manual", name="zone_assignment_type_enum")
zone_assignment_method_enum = sa.Enum(
    "polygon_direct",
    "centroid_fallback",
    "bootstrap_fallback",
    "manual_override",
    name="zone_assignment_method_enum",
)
zone_unassigned_reason_enum = sa.Enum(
    "no_coordinates",
    "no_candidate_zone",
    "polygon_miss",
    "below_threshold",
    name="zone_unassigned_reason_enum",
)
zone_type_table_enum = postgresql.ENUM(
    "bootstrap",
    "system",
    "user",
    name="zone_type_enum",
    create_type=False,
)
zone_assignment_type_table_enum = postgresql.ENUM(
    "auto",
    "manual",
    name="zone_assignment_type_enum",
    create_type=False,
)
zone_assignment_method_table_enum = postgresql.ENUM(
    "polygon_direct",
    "centroid_fallback",
    "bootstrap_fallback",
    "manual_override",
    name="zone_assignment_method_enum",
    create_type=False,
)
zone_unassigned_reason_table_enum = postgresql.ENUM(
    "no_coordinates",
    "no_candidate_zone",
    "polygon_miss",
    "below_threshold",
    name="zone_unassigned_reason_enum",
    create_type=False,
)


def upgrade():
    bind = op.get_bind()
    zone_type_enum.create(bind, checkfirst=True)
    zone_assignment_type_enum.create(bind, checkfirst=True)
    zone_assignment_method_enum.create(bind, checkfirst=True)
    zone_unassigned_reason_enum.create(bind, checkfirst=True)

    if not _has_table("zone_version"):
        op.create_table(
            "zone_version",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("city_key", sa.String(length=255), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "team_id",
                "city_key",
                "version_number",
                name="uq_zone_version_team_city_version",
            ),
        )

    if _has_table("zone_version"):
        if not _has_index("zone_version", "uix_zone_version_active_team_city"):
            op.create_index(
                "uix_zone_version_active_team_city",
                "zone_version",
                ["team_id", "city_key"],
                unique=True,
                postgresql_where=sa.text("is_active IS TRUE"),
            )
        if not _has_index("zone_version", "ix_zone_version_team_city_created"):
            op.create_index(
                "ix_zone_version_team_city_created",
                "zone_version",
                ["team_id", "city_key", "created_at"],
                unique=False,
            )

    if not _has_table("zone"):
        op.create_table(
            "zone",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("zone_version_id", sa.Integer(), nullable=False),
            sa.Column("city_key", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("zone_type", zone_type_table_enum, nullable=False),
            sa.Column("centroid_lat", sa.Float(), nullable=True),
            sa.Column("centroid_lng", sa.Float(), nullable=True),
            sa.Column(
                "geometry",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column("min_lat", sa.Float(), nullable=True),
            sa.Column("max_lat", sa.Float(), nullable=True),
            sa.Column("min_lng", sa.Float(), nullable=True),
            sa.Column("max_lng", sa.Float(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["zone_version_id"], ["zone_version.id"], ondelete="CASCADE"),
        )

    if _has_table("zone"):
        if not _has_index("zone", "ix_zone_team_version_active"):
            op.create_index(
                "ix_zone_team_version_active",
                "zone",
                ["team_id", "zone_version_id", "is_active"],
                unique=False,
            )
        if not _has_index("zone", "ix_zone_team_city_version"):
            op.create_index(
                "ix_zone_team_city_version",
                "zone",
                ["team_id", "city_key", "zone_version_id"],
                unique=False,
            )
        if not _has_index("zone", "ix_zone_bbox_lookup"):
            op.create_index(
                "ix_zone_bbox_lookup",
                "zone",
                [
                    "team_id",
                    "city_key",
                    "zone_version_id",
                    "min_lat",
                    "max_lat",
                    "min_lng",
                    "max_lng",
                ],
                unique=False,
            )

    if not _has_table("order_zone_assignment"):
        op.create_table(
            "order_zone_assignment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("zone_id", sa.Integer(), nullable=True),
            sa.Column("zone_version_id", sa.Integer(), nullable=True),
            sa.Column("city_key", sa.String(length=255), nullable=False),
            sa.Column("assignment_type", zone_assignment_type_table_enum, nullable=False, server_default="auto"),
            sa.Column("assignment_method", zone_assignment_method_table_enum, nullable=True),
            sa.Column("is_unassigned", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("unassigned_reason", zone_unassigned_reason_table_enum, nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["order_id"], ["order.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["zone_id"], ["zone.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["zone_version_id"], ["zone_version.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("order_id", name="uq_order_zone_assignment_order_id"),
        )

    if _has_table("order_zone_assignment"):
        if not _has_index("order_zone_assignment", "ix_order_zone_assignment_scope"):
            op.create_index(
                "ix_order_zone_assignment_scope",
                "order_zone_assignment",
                ["team_id", "city_key", "zone_version_id"],
                unique=False,
            )
        if not _has_index("order_zone_assignment", "ix_order_zone_assignment_unassigned"):
            op.create_index(
                "ix_order_zone_assignment_unassigned",
                "order_zone_assignment",
                ["team_id", "is_unassigned", "assigned_at"],
                unique=False,
            )

    if _has_table("analytics_route_metrics_snapshot") and not _has_column(
        "analytics_route_metrics_snapshot", "zone_version_id"
    ):
        op.add_column(
            "analytics_route_metrics_snapshot",
            sa.Column("zone_version_id", sa.Integer(), nullable=True),
        )

    if _has_table("analytics_route_metrics_snapshot"):
        if not _has_index("analytics_route_metrics_snapshot", "ix_analytics_rms_zone_version_id"):
            op.create_index(
                "ix_analytics_rms_zone_version_id",
                "analytics_route_metrics_snapshot",
                ["zone_version_id"],
                unique=False,
            )
        if not _has_index("analytics_route_metrics_snapshot", "ix_analytics_rms_team_zone_version_zone"):
            op.create_index(
                "ix_analytics_rms_team_zone_version_zone",
                "analytics_route_metrics_snapshot",
                ["team_id", "zone_version_id", "zone_id"],
                unique=False,
            )

    if _has_table("analytics_daily_fact") and not _has_column(
        "analytics_daily_fact", "zone_version_id"
    ):
        op.add_column(
            "analytics_daily_fact",
            sa.Column("zone_version_id", sa.Integer(), nullable=True),
        )

    if _has_table("analytics_daily_fact"):
        if _has_index("analytics_daily_fact", "uix_analytics_daily_zoned"):
            op.drop_index("uix_analytics_daily_zoned", table_name="analytics_daily_fact")
        if _has_index("analytics_daily_fact", "ix_analytics_daily_fact_team_date_zone"):
            op.drop_index("ix_analytics_daily_fact_team_date_zone", table_name="analytics_daily_fact")

        op.create_index(
            "uix_analytics_daily_zoned",
            "analytics_daily_fact",
            ["team_id", "date", "zone_version_id", "zone_id"],
            unique=True,
            postgresql_where=sa.text("zone_id IS NOT NULL"),
        )
        op.create_index(
            "ix_analytics_daily_fact_team_date_zone",
            "analytics_daily_fact",
            ["team_id", "date", "zone_version_id", "zone_id"],
            unique=False,
        )


def downgrade():
    if _has_table("analytics_daily_fact"):
        if _has_index("analytics_daily_fact", "ix_analytics_daily_fact_team_date_zone"):
            op.drop_index("ix_analytics_daily_fact_team_date_zone", table_name="analytics_daily_fact")
        if _has_index("analytics_daily_fact", "uix_analytics_daily_zoned"):
            op.drop_index("uix_analytics_daily_zoned", table_name="analytics_daily_fact")
        op.create_index(
            "uix_analytics_daily_zoned",
            "analytics_daily_fact",
            ["team_id", "date", "zone_id"],
            unique=True,
            postgresql_where=sa.text("zone_id IS NOT NULL"),
        )
        op.create_index(
            "ix_analytics_daily_fact_team_date_zone",
            "analytics_daily_fact",
            ["team_id", "date", "zone_id"],
            unique=False,
        )
        if _has_column("analytics_daily_fact", "zone_version_id"):
            op.drop_column("analytics_daily_fact", "zone_version_id")

    if _has_table("analytics_route_metrics_snapshot"):
        if _has_index("analytics_route_metrics_snapshot", "ix_analytics_rms_team_zone_version_zone"):
            op.drop_index(
                "ix_analytics_rms_team_zone_version_zone",
                table_name="analytics_route_metrics_snapshot",
            )
        if _has_index("analytics_route_metrics_snapshot", "ix_analytics_rms_zone_version_id"):
            op.drop_index(
                "ix_analytics_rms_zone_version_id",
                table_name="analytics_route_metrics_snapshot",
            )
        if _has_column("analytics_route_metrics_snapshot", "zone_version_id"):
            op.drop_column("analytics_route_metrics_snapshot", "zone_version_id")

    if _has_table("order_zone_assignment"):
        if _has_index("order_zone_assignment", "ix_order_zone_assignment_unassigned"):
            op.drop_index("ix_order_zone_assignment_unassigned", table_name="order_zone_assignment")
        if _has_index("order_zone_assignment", "ix_order_zone_assignment_scope"):
            op.drop_index("ix_order_zone_assignment_scope", table_name="order_zone_assignment")
        op.drop_table("order_zone_assignment")

    if _has_table("zone"):
        if _has_index("zone", "ix_zone_bbox_lookup"):
            op.drop_index("ix_zone_bbox_lookup", table_name="zone")
        if _has_index("zone", "ix_zone_team_city_version"):
            op.drop_index("ix_zone_team_city_version", table_name="zone")
        if _has_index("zone", "ix_zone_team_version_active"):
            op.drop_index("ix_zone_team_version_active", table_name="zone")
        op.drop_table("zone")

    if _has_table("zone_version"):
        if _has_index("zone_version", "ix_zone_version_team_city_created"):
            op.drop_index("ix_zone_version_team_city_created", table_name="zone_version")
        if _has_index("zone_version", "uix_zone_version_active_team_city"):
            op.drop_index("uix_zone_version_active_team_city", table_name="zone_version")
        op.drop_table("zone_version")

    bind = op.get_bind()
    zone_unassigned_reason_enum.drop(bind, checkfirst=True)
    zone_assignment_method_enum.drop(bind, checkfirst=True)
    zone_assignment_type_enum.drop(bind, checkfirst=True)
    zone_type_enum.drop(bind, checkfirst=True)