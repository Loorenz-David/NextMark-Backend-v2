"""Phase 1 zone structural foundation.

Revision ID: p7d2c9a4f1e8
Revises: b3c4d5e6f7a8, rc1p1m0d3l99
Create Date: 2026-03-27 11:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "p7d2c9a4f1e8"
down_revision = ("b3c4d5e6f7a8", "rc1p1m0d3l99")
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    inspector = inspect(op.get_bind())
    return table in inspector.get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    inspector = inspect(op.get_bind())
    return any(col.get("name") == column for col in inspector.get_columns(table))


def _has_index(table: str, index_name: str) -> bool:
    if not _has_table(table):
        return False
    inspector = inspect(op.get_bind())
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table))


def _drop_route_group_route_plan_unique_constraints() -> None:
    inspector = inspect(op.get_bind())

    for constraint in inspector.get_unique_constraints("route_group"):
        columns = constraint.get("column_names") or []
        name = constraint.get("name")
        if name and columns == ["route_plan_id"]:
            op.drop_constraint(name, "route_group", type_="unique")

    for index in inspector.get_indexes("route_group"):
        if index.get("column_names") == ["route_plan_id"] and index.get("unique"):
            index_name = index.get("name")
            if index_name:
                op.drop_index(index_name, table_name="route_group")


def upgrade() -> None:
    if _has_table("route_group"):
        _drop_route_group_route_plan_unique_constraints()

        if not _has_index("route_group", "ix_route_group_route_plan_id"):
            op.create_index(
                "ix_route_group_route_plan_id",
                "route_group",
                ["route_plan_id"],
                unique=False,
            )

        if not _has_column("route_group", "zone_id"):
            op.add_column("route_group", sa.Column("zone_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_route_group_zone_id_zone",
                "route_group",
                "zone",
                ["zone_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if not _has_index("route_group", "ix_route_group_zone_id"):
            op.create_index("ix_route_group_zone_id", "route_group", ["zone_id"], unique=False)

        if not _has_column("route_group", "name"):
            op.add_column("route_group", sa.Column("name", sa.String(length=255), nullable=True))

        if not _has_column("route_group", "zone_geometry_snapshot"):
            op.add_column(
                "route_group",
                sa.Column(
                    "zone_geometry_snapshot",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=True,
                ),
            )

        if not _has_column("route_group", "template_snapshot"):
            op.add_column(
                "route_group",
                sa.Column(
                    "template_snapshot",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=True,
                ),
            )

    if not _has_table("zone_template"):
        op.create_table(
            "zone_template",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("zone_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column(
                "config_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
            ),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["zone_id"], ["zone.id"], ondelete="CASCADE"),
        )

    if _has_table("zone_template"):
        if not _has_index("zone_template", "ix_zone_template_team_id"):
            op.create_index("ix_zone_template_team_id", "zone_template", ["team_id"], unique=False)
        if not _has_index("zone_template", "ix_zone_template_zone_id"):
            op.create_index("ix_zone_template_zone_id", "zone_template", ["zone_id"], unique=False)


def downgrade() -> None:
    if _has_table("zone_template"):
        if _has_index("zone_template", "ix_zone_template_zone_id"):
            op.drop_index("ix_zone_template_zone_id", table_name="zone_template")
        if _has_index("zone_template", "ix_zone_template_team_id"):
            op.drop_index("ix_zone_template_team_id", table_name="zone_template")
        op.drop_table("zone_template")

    if _has_table("route_group"):
        if _has_column("route_group", "template_snapshot"):
            op.drop_column("route_group", "template_snapshot")

        if _has_column("route_group", "zone_geometry_snapshot"):
            op.drop_column("route_group", "zone_geometry_snapshot")

        if _has_column("route_group", "name"):
            op.drop_column("route_group", "name")

        if _has_index("route_group", "ix_route_group_zone_id"):
            op.drop_index("ix_route_group_zone_id", table_name="route_group")
        if _has_column("route_group", "zone_id"):
            op.drop_constraint("fk_route_group_zone_id_zone", "route_group", type_="foreignkey")
            op.drop_column("route_group", "zone_id")

        if _has_index("route_group", "ix_route_group_route_plan_id"):
            op.drop_index("ix_route_group_route_plan_id", table_name="route_group")

        op.create_unique_constraint(
            "uq_route_group_route_plan_id",
            "route_group",
            ["route_plan_id"],
        )
