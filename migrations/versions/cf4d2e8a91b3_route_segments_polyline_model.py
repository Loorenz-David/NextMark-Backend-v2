""" route segments polyline model

Revision ID: cf4d2e8a91b3
Revises: 134a055dd777
Create Date: 2026-02-27 21:20:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "cf4d2e8a91b3"
down_revision = "134a055dd777"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("route_solution", schema=None) as batch_op:
        batch_op.add_column(sa.Column("start_leg_polyline", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        batch_op.add_column(sa.Column("end_leg_polyline", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        batch_op.drop_column("route_polyline")

    with op.batch_alter_table("route_solution_stop", schema=None) as batch_op:
        batch_op.add_column(sa.Column("to_next_polyline", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    with op.batch_alter_table("route_solution_stop", schema=None) as batch_op:
        batch_op.drop_column("to_next_polyline")

    with op.batch_alter_table("route_solution", schema=None) as batch_op:
        batch_op.add_column(sa.Column("route_polyline", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        batch_op.drop_column("end_leg_polyline")
        batch_op.drop_column("start_leg_polyline")
