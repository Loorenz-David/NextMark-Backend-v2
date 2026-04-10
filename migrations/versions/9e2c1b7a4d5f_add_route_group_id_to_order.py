"""add_route_group_id_to_order

Revision ID: 9e2c1b7a4d5f
Revises: 79738f41626f
Create Date: 2026-03-27 23:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9e2c1b7a4d5f"
down_revision = "79738f41626f"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("order", schema=None) as batch_op:
        batch_op.add_column(sa.Column("route_group_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_order_route_group_id", ["route_group_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_order_route_group_id",
            "route_group",
            ["route_group_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Backfill only unambiguous assignments from existing stops.
    op.execute(
        sa.text(
            """
            WITH stop_groups AS (
                SELECT
                    rss.order_id AS order_id,
                    MIN(rs.route_group_id) AS route_group_id,
                    COUNT(DISTINCT rs.route_group_id) AS group_count
                FROM route_solution_stop rss
                JOIN route_solution rs ON rs.id = rss.route_solution_id
                WHERE rss.order_id IS NOT NULL
                  AND rs.route_group_id IS NOT NULL
                GROUP BY rss.order_id
            )
            UPDATE "order" o
            SET route_group_id = sg.route_group_id
            FROM stop_groups sg
            WHERE o.id = sg.order_id
              AND sg.group_count = 1
              AND o.route_group_id IS NULL
            """
        )
    )

    # Ensure route_group assignment stays consistent with order.route_plan_id.
    op.execute(
        sa.text(
            """
            UPDATE "order" o
            SET route_group_id = NULL
            FROM route_group rg
            WHERE o.route_group_id = rg.id
              AND o.route_plan_id IS NOT NULL
              AND rg.route_plan_id IS NOT NULL
              AND o.route_plan_id <> rg.route_plan_id
            """
        )
    )


def downgrade():
    with op.batch_alter_table("order", schema=None) as batch_op:
        batch_op.drop_constraint("fk_order_route_group_id", type_="foreignkey")
        batch_op.drop_index("ix_order_route_group_id")
        batch_op.drop_column("route_group_id")
