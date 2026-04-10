"""add_partial_unique_index_for_no_zone_route_group

Revision ID: d8e3f1a4b2c7
Revises: c2b4d8e1f0a9
Create Date: 2026-03-28 10:42:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d8e3f1a4b2c7"
down_revision = "c2b4d8e1f0a9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_route_group_unassigned_bucket_per_plan",
        "route_group",
        ["team_id", "route_plan_id"],
        unique=True,
        postgresql_where=sa.text("zone_id IS NULL"),
    )


def downgrade():
    op.drop_index(
        "uq_route_group_unassigned_bucket_per_plan",
        table_name="route_group",
    )
