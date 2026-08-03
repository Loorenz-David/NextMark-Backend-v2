"""add plan_type to route_plan

Makes the planning domain that owns a plan explicit instead of inferring it from
which child rows happen to exist. Every existing plan is local delivery, so the
column is backfilled with that value via a server default which is then dropped —
new rows must state their type at the application layer.

Revision ID: e3f4a5b6c7d8
Revises: d1e2f3a4b5c6
Create Date: 2026-08-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "e3f4a5b6c7d8"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_index(table: str, index: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(i["name"] == index for i in inspector.get_indexes(table))


def upgrade() -> None:
    if not _has_column("route_plan", "plan_type"):
        with op.batch_alter_table("route_plan", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "plan_type",
                    sa.String(),
                    nullable=False,
                    server_default="local_delivery",
                )
            )

    if not _has_index("route_plan", "ix_route_plan_plan_type"):
        with op.batch_alter_table("route_plan", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_route_plan_plan_type"),
                ["plan_type"],
                unique=False,
            )

    # Existing rows are backfilled by the server default above. Drop it so new
    # rows cannot silently inherit a type they never declared.
    with op.batch_alter_table("route_plan", schema=None) as batch_op:
        batch_op.alter_column("plan_type", server_default=None)


def downgrade() -> None:
    if _has_index("route_plan", "ix_route_plan_plan_type"):
        with op.batch_alter_table("route_plan", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_route_plan_plan_type"))

    if _has_column("route_plan", "plan_type"):
        with op.batch_alter_table("route_plan", schema=None) as batch_op:
            batch_op.drop_column("plan_type")
