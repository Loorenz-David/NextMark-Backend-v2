"""add unique route stop order per route

Revision ID: p4r8s2t6u1v5
Revises: m2p7q1w8x4y6
Create Date: 2026-03-19 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p4r8s2t6u1v5"
down_revision = "m2p7q1w8x4y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH ordered_stops AS (
            SELECT
                id,
                route_solution_id,
                ROW_NUMBER() OVER (
                    PARTITION BY route_solution_id
                    ORDER BY
                        CASE WHEN stop_order IS NULL THEN 1 ELSE 0 END,
                        stop_order,
                        id
                ) AS normalized_stop_order
            FROM route_solution_stop
        )
        UPDATE route_solution_stop AS target
        SET stop_order = ordered_stops.normalized_stop_order
        FROM ordered_stops
        WHERE target.id = ordered_stops.id
          AND target.stop_order IS DISTINCT FROM ordered_stops.normalized_stop_order
        """
    )

    op.execute(
        """
        UPDATE route_solution AS route
        SET stop_count = counts.stop_count
        FROM (
            SELECT
                route_solution_id,
                COUNT(*)::integer AS stop_count
            FROM route_solution_stop
            GROUP BY route_solution_id
        ) AS counts
        WHERE route.id = counts.route_solution_id
        """
    )

    op.execute(
        """
        UPDATE route_solution
        SET stop_count = 0
        WHERE id NOT IN (
            SELECT DISTINCT route_solution_id
            FROM route_solution_stop
        )
        """
    )

    op.create_index(
        "uq_route_solution_stop_route_solution_id_stop_order",
        "route_solution_stop",
        ["route_solution_id", "stop_order"],
        unique=True,
        postgresql_where=sa.text("stop_order IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_route_solution_stop_route_solution_id_stop_order",
        table_name="route_solution_stop",
    )
