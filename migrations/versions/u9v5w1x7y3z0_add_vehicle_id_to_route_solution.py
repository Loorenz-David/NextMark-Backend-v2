"""Add vehicle_id FK column to route_solution table.

Revision ID: u9v5w1x7y3z0
Revises: t8u4v0w6x2y9
Create Date: 2025-01-03 00:00:01.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "u9v5w1x7y3z0"
down_revision = "t8u4v0w6x2y9"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade():
    if not _has_column("route_solution", "vehicle_id"):
        op.add_column(
            "route_solution",
            sa.Column(
                "vehicle_id",
                sa.Integer(),
                sa.ForeignKey("vehicle.id"),
                nullable=True,
            ),
        )


def downgrade():
    if _has_column("route_solution", "vehicle_id"):
        try:
            op.drop_constraint(
                "route_solution_vehicle_id_fkey", "route_solution", type_="foreignkey"
            )
        except Exception:
            pass
        op.drop_column("route_solution", "vehicle_id")
