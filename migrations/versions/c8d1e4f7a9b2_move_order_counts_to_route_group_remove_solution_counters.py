"""move order counters to route_group and drop route_solution counters

Revision ID: c8d1e4f7a9b2
Revises: b7a3c9d4e1f2
Create Date: 2026-03-28 16:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c8d1e4f7a9b2"
down_revision = "b7a3c9d4e1f2"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def upgrade():
    with op.batch_alter_table("route_group", schema=None) as batch_op:
        if not _has_column("route_group", "order_state_counts"):
            batch_op.add_column(
                sa.Column(
                    "order_state_counts",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=True,
                )
            )

    with op.batch_alter_table("route_solution", schema=None) as batch_op:
        if _has_column("route_solution", "order_state_counts"):
            batch_op.drop_column("order_state_counts")
        if _has_column("route_solution", "order_count"):
            batch_op.drop_column("order_count")
        if _has_column("route_solution", "stop_count"):
            batch_op.drop_column("stop_count")


def downgrade():
    with op.batch_alter_table("route_solution", schema=None) as batch_op:
        if not _has_column("route_solution", "stop_count"):
            batch_op.add_column(
                sa.Column("stop_count", sa.Integer(), nullable=True, server_default="0")
            )
        if not _has_column("route_solution", "order_count"):
            batch_op.add_column(
                sa.Column("order_count", sa.Integer(), nullable=True, server_default="0")
            )
        if not _has_column("route_solution", "order_state_counts"):
            batch_op.add_column(
                sa.Column(
                    "order_state_counts",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=True,
                )
            )

    with op.batch_alter_table("route_group", schema=None) as batch_op:
        if _has_column("route_group", "order_state_counts"):
            batch_op.drop_column("order_state_counts")
