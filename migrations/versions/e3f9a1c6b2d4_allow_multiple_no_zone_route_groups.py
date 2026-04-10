"""allow_multiple_no_zone_route_groups

Revision ID: e3f9a1c6b2d4
Revises: d8e3f1a4b2c7
Create Date: 2026-03-28 11:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e3f9a1c6b2d4"
down_revision = "d8e3f1a4b2c7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "route_group",
        sa.Column(
            "is_system_default_bucket",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_route_group_is_system_default_bucket",
        "route_group",
        ["is_system_default_bucket"],
        unique=False,
    )

    # Existing no-zone groups are the legacy default bucket in each plan.
    op.execute(
        """
        UPDATE route_group
        SET is_system_default_bucket = true
        WHERE zone_id IS NULL
        """
    )

    op.execute("DROP INDEX IF EXISTS uq_route_group_unassigned_bucket_per_plan")
    op.create_index(
        "uq_route_group_system_default_bucket_per_plan",
        "route_group",
        ["team_id", "route_plan_id"],
        unique=True,
        postgresql_where=sa.text("zone_id IS NULL AND is_system_default_bucket IS TRUE"),
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_route_group_system_default_bucket_per_plan")
    op.create_index(
        "uq_route_group_unassigned_bucket_per_plan",
        "route_group",
        ["team_id", "route_plan_id"],
        unique=True,
        postgresql_where=sa.text("zone_id IS NULL"),
    )

    op.drop_index("ix_route_group_is_system_default_bucket", table_name="route_group")
    op.drop_column("route_group", "is_system_default_bucket")
