"""add order_count and order_state_counts to route_solution

Revision ID: z1a5b9c3d7e2
Revises: 6ab37933bdd2
Create Date: 2026-03-24 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "z1a5b9c3d7e2"
down_revision = "6ab37933bdd2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("route_solution", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("order_count", sa.Integer(), nullable=True, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "order_state_counts",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("route_solution", schema=None) as batch_op:
        batch_op.drop_column("order_state_counts")
        batch_op.drop_column("order_count")
