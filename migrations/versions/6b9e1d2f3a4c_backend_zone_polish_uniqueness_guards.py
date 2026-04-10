"""Backend zone polish uniqueness guards.

Revision ID: 6b9e1d2f3a4c
Revises: 23fe71afdb5d
Create Date: 2026-03-27 12:35:00.000000
"""

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "6b9e1d2f3a4c"
down_revision = "23fe71afdb5d"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    inspector = inspect(op.get_bind())
    return table in inspector.get_table_names()


def _has_index(table: str, index_name: str) -> bool:
    if not _has_table(table):
        return False
    inspector = inspect(op.get_bind())
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table))


def _has_unique_constraint(table: str, constraint_name: str) -> bool:
    if not _has_table(table):
        return False
    inspector = inspect(op.get_bind())
    return any(c.get("name") == constraint_name for c in inspector.get_unique_constraints(table))


def upgrade() -> None:
    if _has_table("route_group") and not _has_unique_constraint("route_group", "uq_route_group_team_plan_zone"):
        op.create_unique_constraint(
            "uq_route_group_team_plan_zone",
            "route_group",
            ["team_id", "route_plan_id", "zone_id"],
        )

    if _has_table("zone_template") and not _has_index("zone_template", "uq_zone_template_active_per_zone"):
        op.execute(
            "CREATE UNIQUE INDEX uq_zone_template_active_per_zone "
            "ON zone_template (team_id, zone_id) WHERE is_active = true"
        )


def downgrade() -> None:
    if _has_table("zone_template") and _has_index("zone_template", "uq_zone_template_active_per_zone"):
        op.execute("DROP INDEX uq_zone_template_active_per_zone")

    if _has_table("route_group") and _has_unique_constraint("route_group", "uq_route_group_team_plan_zone"):
        op.drop_constraint("uq_route_group_team_plan_zone", "route_group", type_="unique")
